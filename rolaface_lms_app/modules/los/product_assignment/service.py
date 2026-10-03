from typing import Any, Dict, List, Tuple

import frappe

from ..common import (
	build_order_by,
	count_records,
	dump_json,
	ensure_status_change,
	json_contains,
	load_json,
	name_map,
	parse_flag,
	search_or_filters,
)
from .constant import (
	ALLOWED_SORT_FIELDS,
	CHANNEL_DOCTYPE,
	LEVEL_LOAN_TYPE,
	LEVEL_PURPOSE,
	LIST_OPERATORS,
	LOAN_PRODUCT_DOCTYPE,
	NO_MATCH_DEFAULT_PRODUCT,
	NUMBER_OPERATORS,
	RETURN_FIELDS_GET_ALL,
	RETURN_FIELDS_GET_BY_ID,
	RULE_DOCTYPE,
	SEARCH_FIELDS,
	SETTINGS_DOCTYPE,
	SETTINGS_FIELDS,
	STATUS_CONFLICT,
	STATUS_LOAN_TYPE_DEFAULT,
	STATUS_MANUAL_REVIEW,
	STATUS_RULE_MATCHED,
	TREE_DOCTYPE,
	VARIABLES,
)
from .utils import (
	build_rule_filters,
	evaluate_condition,
	load_references,
	parse_rule_row,
	validate_new_product,
	validate_rule,
	validate_settings,
	validate_update_payload,
)


def _read_settings() -> Dict[str, Any]:
	stored = frappe.db.get_singles_dict(SETTINGS_DOCTYPE)
	meta = frappe.get_meta(SETTINGS_DOCTYPE)
	return {
		"several_match": stored.get("several_match") or meta.get_field("several_match").default,
		"no_match": stored.get("no_match") or meta.get_field("no_match").default,
		"default_product": load_json(stored.get("default_product"), {}) or {},
	}


def get_settings() -> Dict[str, Any]:
	settings = _read_settings()
	defaults = settings["default_product"]
	loan_type_names = name_map(TREE_DOCTYPE, defaults.keys(), "node_name")
	product_names = name_map(LOAN_PRODUCT_DOCTYPE, defaults.values(), "product_name")

	settings["default_product_list"] = [
		{
			"loan_type": loan_type,
			"loan_type_name": loan_type_names.get(loan_type),
			"product": product,
			"product_name": product_names.get(product),
		}
		for loan_type, product in defaults.items()
	]
	return settings


def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
	stored = _read_settings()
	settings = dict(stored, default_product=dict(stored["default_product"]))
	for field in SETTINGS_FIELDS:
		if data.get(field) is not None:
			settings[field] = data.get(field)

	settings = validate_settings(settings, load_references(), stored["default_product"])
	if any(settings[field] != stored[field] for field in SETTINGS_FIELDS):
		settings_doc = frappe.get_single(SETTINGS_DOCTYPE)
		settings_doc.several_match = settings["several_match"]
		settings_doc.no_match = settings["no_match"]
		settings_doc.default_product = dump_json(settings["default_product"])
		settings_doc.save(ignore_permissions=True)
	return get_settings()


def _ensure_exists(rule_id: str) -> Dict[str, Any]:
	row = frappe.db.get_value(RULE_DOCTYPE, rule_id, RETURN_FIELDS_GET_ALL, as_dict=True)
	if not row:
		raise frappe.DoesNotExistError(f"Loan Product '{rule_id}' has no assignment rule.")
	return parse_rule_row(row)


def _set_rule_values(rule_doc, values: Dict[str, Any]):
	rule_doc.sources = dump_json(values["sources"])
	rule_doc.loan_types = dump_json(values["loan_types"])
	rule_doc.condition = dump_json(values["condition"])


def _add_rule_names(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	channels = name_map(CHANNEL_DOCTYPE, [s for r in rules for s in r["sources"]], "channel_name")
	loan_types = name_map(TREE_DOCTYPE, [lt for r in rules for lt in r["loan_types"]], "node_name")
	for rule in rules:
		rule["source_names"] = [channels.get(s) for s in rule["sources"]]
		rule["loan_type_names"] = [loan_types.get(lt) for lt in rule["loan_types"]]
		rule["has_condition"] = 1 if rule.get("condition") else 0
	return rules


def create_rule(data: Dict[str, Any]) -> Dict[str, Any]:
	refs = load_references()
	product = validate_new_product(data, refs)
	values = validate_rule(data, refs)

	rule_doc = frappe.new_doc(RULE_DOCTYPE)
	rule_doc.product = product
	rule_doc.is_active = 1 if data.get("is_active") is None else parse_flag(data.get("is_active"), "is_active")
	_set_rule_values(rule_doc, values)
	rule_doc.insert(ignore_permissions=True)
	return get_rule_by_id(rule_doc.name)


def update_rule(rule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	current = _ensure_exists(rule_id)
	validate_update_payload(data, rule_id)

	merged = {**current, **{field: data[field] for field in ("sources", "loan_types", "condition") if field in data}}
	values = validate_rule(merged, load_references(), current=current)
	if any(values[field] != current.get(field) for field in values):
		rule_doc = frappe.get_doc(RULE_DOCTYPE, rule_id)
		_set_rule_values(rule_doc, values)
		rule_doc.save(ignore_permissions=True)
	return get_rule_by_id(rule_id)


def get_rule_by_id(rule_id: str) -> Dict[str, Any]:
	rule = frappe.db.get_value(RULE_DOCTYPE, rule_id, RETURN_FIELDS_GET_BY_ID, as_dict=True)
	if not rule:
		raise frappe.DoesNotExistError(f"Loan Product '{rule_id}' has no assignment rule.")
	return _add_rule_names([parse_rule_row(rule)])[0]


def get_rules(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int]:
	filters = build_rule_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS)
	order_by = build_order_by(RULE_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS)

	rules = frappe.get_all(
		RULE_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	return _add_rule_names([parse_rule_row(r) for r in rules]), count_records(RULE_DOCTYPE, filters, or_filters)


def delete_rule(rule_id: str):
	_ensure_exists(rule_id)
	frappe.delete_doc(RULE_DOCTYPE, rule_id, ignore_permissions=True)


def toggle_rule_status(rule_id: str, is_active: int) -> Dict[str, Any]:
	rule = _ensure_exists(rule_id)
	ensure_status_change(rule.is_active, is_active, f"The rule for '{rule.product_name or rule.name}'")

	rule_doc = frappe.get_doc(RULE_DOCTYPE, rule_id)
	rule_doc.is_active = is_active
	rule_doc.save(ignore_permissions=True)
	return {"name": rule.name, "product_name": rule.product_name, "is_active": is_active}


def test_rules(data: Dict[str, Any]) -> Dict[str, Any]:
	source = str(data.get("source") or "").strip()
	if not source:
		raise frappe.ValidationError("source is required.")
	channel = frappe.db.get_value(CHANNEL_DOCTYPE, source, ["channel_name", "is_active"], as_dict=True)
	if not channel:
		raise frappe.DoesNotExistError(f"Channel '{source}' does not exist.")
	if not channel.is_active:
		raise frappe.ValidationError(f"Channel '{channel.channel_name}' is inactive.")

	loan_type = _resolve_loan_type(data)
	facts = load_json(data.get("facts"), {}) or {}
	if not isinstance(facts, dict):
		raise frappe.ValidationError("facts must be an object.")
	unknown = [key for key in facts if key not in VARIABLES]
	if unknown:
		raise frappe.ValidationError(f"Unknown facts: {', '.join(unknown)}. Allowed: {', '.join(VARIABLES)}.")

	settings = _read_settings()
	candidates = frappe.get_all(
		RULE_DOCTYPE,
		filters=[["is_active", "=", 1], json_contains("sources", source), json_contains("loan_types", loan_type)],
		fields=RETURN_FIELDS_GET_ALL,
		limit_page_length=0,
	)
	products = {c.product for c in candidates} | set(settings["default_product"].values())
	enabled_products = (
		set(frappe.get_all(LOAN_PRODUCT_DOCTYPE, filters={"disabled": 0, "name": ["in", list(products)]}, pluck="name"))
		if products
		else set()
	)
	matches = [
		rule
		for rule in map(parse_rule_row, candidates)
		if source in rule["sources"]
		and loan_type in rule["loan_types"]
		and rule["product"] in enabled_products
		and evaluate_condition(rule["condition"], facts)
	]
	default_product = settings["default_product"].get(loan_type)

	result = {"source": source, "loan_type": loan_type, "matched_rules": [], "product": None}
	if len(matches) == 1:
		result.update(status=STATUS_RULE_MATCHED, product=matches[0].product)
	elif matches:
		result.update(
			status=STATUS_CONFLICT,
			reason="More than one product's rule matches. Change the rules so only one product matches.",
		)
	elif settings["no_match"] == NO_MATCH_DEFAULT_PRODUCT and default_product in enabled_products:
		result.update(status=STATUS_LOAN_TYPE_DEFAULT, product=default_product)
	else:
		result.update(status=STATUS_MANUAL_REVIEW, reason="No rule matches and this loan type has no enabled default product.")

	result["matched_rules"] = [{"product": r.product, "product_name": r.product_name} for r in matches]
	result["product_name"] = (
		frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, result["product"], "product_name") if result["product"] else None
	)
	return result


def _resolve_loan_type(data: Dict[str, Any]) -> str:
	loan_type, purpose = data.get("loan_type"), data.get("purpose")
	if purpose:
		node = frappe.db.get_value(TREE_DOCTYPE, purpose, ["node_name", "level", "loan_type", "is_active"], as_dict=True)
		if not node:
			raise frappe.DoesNotExistError(f"Purpose '{purpose}' does not exist.")
		if node.level != LEVEL_PURPOSE:
			raise frappe.ValidationError(f"'{node.node_name}' is not a purpose.")
		if not node.is_active:
			raise frappe.ValidationError(f"Purpose '{node.node_name}' is inactive.")
		if loan_type and loan_type != node.loan_type:
			raise frappe.ValidationError("purpose does not belong to the given loan_type.")
		return node.loan_type

	if not loan_type:
		raise frappe.ValidationError("loan_type or purpose is required.")
	node = frappe.db.get_value(TREE_DOCTYPE, loan_type, ["node_name", "level", "is_active"], as_dict=True)
	if not node:
		raise frappe.DoesNotExistError(f"Loan type '{loan_type}' does not exist.")
	if node.level != LEVEL_LOAN_TYPE:
		raise frappe.ValidationError(f"'{node.node_name}' is not a loan type.")
	if not node.is_active:
		raise frappe.ValidationError(f"Loan type '{node.node_name}' is inactive.")
	return loan_type


def get_condition_variables() -> List[Dict[str, Any]]:
	return [
		{
			"name": name,
			"label": spec["label"],
			"numeric": spec["numeric"],
			"operators": list(NUMBER_OPERATORS if spec["numeric"] else LIST_OPERATORS),
			"options": list(spec.get("options") or []),
		}
		for name, spec in VARIABLES.items()
	]
