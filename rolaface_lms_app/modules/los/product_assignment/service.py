from typing import Any, Dict, List, Optional, Tuple

import frappe

from ..common import (
	build_order_by,
	check_version,
	count_records,
	dump_json,
	ensure_status_change,
	json_contains,
	load_json,
	name_map,
	parse_flag,
	search_or_filters,
	single_modified,
	table_version,
	validate_update_fields,
)
from .constant import (
	ALLOWED_RULE_FIELDS,
	ALLOWED_SORT_FIELDS_RULE,
	CHANNEL_DOCTYPE,
	LEVEL_LOAN_TYPE,
	LIST_OPERATORS,
	LEVEL_PURPOSE,
	LOAN_PRODUCT_DOCTYPE,
	MATCH_FIRST,
	NO_MATCH_DEFAULT_PRODUCT,
	NUMBER_OPERATORS,
	RETURN_FIELDS_GET_ALL_RULE,
	RETURN_FIELDS_GET_BY_ID_RULE,
	RULE_DOCTYPE,
	SEARCH_FIELDS_RULE,
	SETTINGS_DOCTYPE,
	SETTINGS_FIELDS,
	STATUS_LOAN_TYPE_DEFAULT,
	STATUS_MANUAL_REVIEW,
	STATUS_RULE_MATCHED,
	TREE_DOCTYPE,
	VARIABLES,
)
from .utils import (
	build_rule_filters,
	evaluate_condition,
	find_shadowed,
	load_references,
	parse_rule_row,
	validate_rule,
	validate_settings,
)

# ---------------------------------------------------------------- Settings


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


def update_settings(data: Dict[str, Any], refs: Optional[Dict] = None) -> Dict[str, Any]:
	settings = _read_settings()
	stored_defaults = dict(settings["default_product"])
	for field in SETTINGS_FIELDS:
		if data.get(field) is not None:
			settings[field] = data.get(field)

	settings = validate_settings(settings, refs or load_references(), stored_defaults)

	settings_doc = frappe.get_single(SETTINGS_DOCTYPE)
	settings_doc.several_match = settings["several_match"]
	settings_doc.no_match = settings["no_match"]
	settings_doc.default_product = dump_json(settings["default_product"])
	settings_doc.save(ignore_permissions=True)
	return get_settings()


# ---------------------------------------------------------------- Rules


def _next_priority() -> int:
	highest = frappe.get_all(RULE_DOCTYPE, fields=["priority"], order_by="priority desc", limit_page_length=1)
	return (highest[0].priority or 0) + 1 if highest else 1


def _set_rule_values(rule_doc, values: Dict[str, Any]):
	rule_doc.rule_name = values["rule_name"]
	rule_doc.product = values["product"]
	rule_doc.sources = dump_json(values["sources"])
	rule_doc.loan_types = dump_json(values["loan_types"])
	rule_doc.condition = dump_json(values["condition"])


def _add_rule_names(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	"""Adds product, channel and loan type names, with 3 queries for any number of rules."""
	products = name_map(LOAN_PRODUCT_DOCTYPE, [r["product"] for r in rules], "product_name")
	channels = name_map(CHANNEL_DOCTYPE, [s for r in rules for s in r["sources"]], "channel_name")
	loan_types = name_map(TREE_DOCTYPE, [lt for r in rules for lt in r["loan_types"]], "node_name")
	for rule in rules:
		rule["product_name"] = products.get(rule["product"])
		rule["source_names"] = [channels.get(s) for s in rule["sources"]]
		rule["loan_type_names"] = [loan_types.get(lt) for lt in rule["loan_types"]]
		rule["has_condition"] = 1 if rule.get("condition") else 0
	return rules


# The per-rule endpoints and the whole-page save both write through these two.


def _save_rule(rule_id: Optional[str], values: Dict[str, Any], priority: Optional[int], is_active: int = 1) -> str:
	"""Inserts (rule_id None) or updates a rule with already validated values. Status is only set on insert."""
	rule_doc = frappe.get_doc(RULE_DOCTYPE, rule_id) if rule_id else frappe.new_doc(RULE_DOCTYPE)
	_set_rule_values(rule_doc, values)
	if not rule_id:
		rule_doc.is_active = is_active
	if priority:
		rule_doc.priority = priority
	if rule_id:
		rule_doc.save(ignore_permissions=True)
	else:
		rule_doc.insert(ignore_permissions=True)
	return rule_doc.name


def _delete_rule(rule_id: str):
	frappe.delete_doc(RULE_DOCTYPE, rule_id, ignore_permissions=True)


def _stored_rule(rule_id: str) -> Dict[str, Any]:
	row = frappe.db.get_value(RULE_DOCTYPE, rule_id, RETURN_FIELDS_GET_ALL_RULE, as_dict=True)
	if not row:
		raise frappe.DoesNotExistError(f"Product assignment rule '{rule_id}' does not exist.")
	return parse_rule_row(row)


def create_rule(data: Dict[str, Any]) -> Dict[str, Any]:
	values = validate_rule(data, load_references())
	is_active = 1 if data.get("is_active") is None else parse_flag(data.get("is_active"), "is_active")
	rule_id = _save_rule(None, values, _clean_priority(data.get("priority")) or _next_priority(), is_active)
	return get_rule_by_id(rule_id)


def update_rule(rule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	current = _stored_rule(rule_id)
	validate_update_fields(data, ALLOWED_RULE_FIELDS, "rule")

	# Validate the rule as it will look after the change, so partial updates stay consistent.
	merged = {**current, **{k: v for k, v in data.items() if k in ALLOWED_RULE_FIELDS}}
	_save_rule(rule_id, validate_rule(merged, load_references(), current=current), _clean_priority(data.get("priority")))
	return get_rule_by_id(rule_id)


def toggle_rule_status(rule_id: str, is_active: int) -> Dict[str, Any]:
	rule = _stored_rule(rule_id)
	label = f"Rule '{rule.rule_name}'" if rule.rule_name else f"Rule {rule.name}"
	ensure_status_change(rule.is_active, is_active, label)

	# Save the document (not db.set_value) so the change shows in the rule's version history.
	rule_doc = frappe.get_doc(RULE_DOCTYPE, rule_id)
	rule_doc.is_active = is_active
	rule_doc.save(ignore_permissions=True)
	return {"name": rule.name, "rule_name": rule.rule_name, "priority": rule.priority, "is_active": is_active}


def _clean_priority(value) -> Optional[int]:
	if value is None or value == "":
		return None
	try:
		priority = int(value)
	except (TypeError, ValueError):
		raise frappe.ValidationError("priority must be a whole number.")
	if priority < 1:
		raise frappe.ValidationError("priority must be 1 or more.")
	return priority


def get_rule_by_id(rule_id: str) -> Dict[str, Any]:
	rule = frappe.db.get_value(RULE_DOCTYPE, rule_id, RETURN_FIELDS_GET_BY_ID_RULE, as_dict=True)
	if not rule:
		raise frappe.DoesNotExistError(f"Product assignment rule '{rule_id}' does not exist.")
	return _add_rule_names([parse_rule_row(rule)])[0]


def get_rules(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int, int]:
	filters = build_rule_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS_RULE)
	order_by = build_order_by(RULE_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS_RULE, tie_breaker="creation")

	rules = frappe.get_all(
		RULE_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL_RULE,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)

	total_records = count_records(RULE_DOCTYPE, filters, or_filters)
	total_pages = (total_records + page_size - 1) // page_size
	return _add_rule_names([parse_rule_row(r) for r in rules]), total_records, total_pages


def _all_rules() -> List[Dict[str, Any]]:
	rows = frappe.get_all(
		RULE_DOCTYPE, fields=RETURN_FIELDS_GET_ALL_RULE, order_by="priority asc, creation asc", limit_page_length=0
	)
	return [parse_rule_row(r) for r in rows]


def delete_rule(rule_id: str):
	_stored_rule(rule_id)
	_delete_rule(rule_id)


# ---------------------------------------------------------------- Whole page


def _page_version() -> str:
	return table_version(RULE_DOCTYPE, single_modified(SETTINGS_DOCTYPE))


def get_product_assignment() -> Dict[str, Any]:
	"""Everything the Product Assignment screen needs, in one call, plus the version the save must send back."""
	rules = _add_rule_names(_all_rules())
	return {
		"settings": get_settings(),
		"rules": rules,
		"warnings": find_shadowed(rules),
		"total_rules": len(rules),
		"version": _page_version(),
	}


def save_product_assignment(data: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Saves the screen in one go: settings plus the full ordered rule list.
	Rules with an existing "name" are updated, rules without one are created (active),
	and stored rules missing from the list are deleted. A rule keeps its active/inactive status.
	Nothing is written if any rule is invalid, or if the page changed since the caller loaded it (version).
	"""
	check_version(data.get("version"), _page_version(), "get_product_assignment")
	refs = load_references()
	rules_payload = load_json(data.get("rules"), None)
	if rules_payload is not None and not isinstance(rules_payload, list):
		raise frappe.ValidationError("rules must be a list.")

	settings_payload = {field: data.get(field) for field in SETTINGS_FIELDS if data.get(field) is not None}
	if settings_payload:
		update_settings(settings_payload, refs)

	if rules_payload is None:
		return get_product_assignment()

	existing = {rule.name: rule for rule in _all_rules()}
	cleaned = []
	for index, rule in enumerate(rules_payload):
		if not isinstance(rule, dict):
			raise frappe.ValidationError(f"Rule {index + 1}: must be an object.")
		rule_id = rule.get("name")
		if rule_id and rule_id not in existing:
			raise frappe.ValidationError(f"Rule {index + 1}: '{rule_id}' does not exist.")
		if rule_id and any(rule_id == seen for seen, _ in cleaned):
			raise frappe.ValidationError(f"Rule {index + 1}: '{rule_id}' appears twice.")
		cleaned.append((rule_id, validate_rule(rule, refs, index, current=existing.get(rule_id))))

	kept = {rule_id for rule_id, _ in cleaned if rule_id}
	for rule_id in set(existing) - kept:
		_delete_rule(rule_id)

	for position, (rule_id, values) in enumerate(cleaned, start=1):
		_save_rule(rule_id, values, position)

	return get_product_assignment()


# ---------------------------------------------------------------- Resolve


def resolve_product(data: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Picks the product for an application: source (channel ID), loan type or purpose (tree ID), and facts
	for the conditions (customer_type, credit_score, loan_amount, ...). Also powers a test panel.
	"""
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

	# Narrow in SQL to active rules for this source and loan type, then check conditions in priority order.
	candidates = frappe.get_all(
		RULE_DOCTYPE,
		filters=[["is_active", "=", 1], json_contains("sources", source), json_contains("loan_types", loan_type)],
		fields=RETURN_FIELDS_GET_ALL_RULE,
		order_by="priority asc, creation asc",
		limit_page_length=0,
	)
	matches = [
		rule
		for rule in map(parse_rule_row, candidates)
		if source in rule["sources"] and loan_type in rule["loan_types"] and evaluate_condition(rule["condition"], facts)
	]

	result = {"source": source, "loan_type": loan_type, "matched_rules": [], "product": None, "rule": None}

	if matches:
		result["matched_rules"] = [{"name": r.name, "rule_name": r.rule_name, "product": r.product} for r in matches]
		if settings["several_match"] == MATCH_FIRST or len(matches) == 1:
			result.update(status=STATUS_RULE_MATCHED, product=matches[0].product, rule=matches[0].name)
		else:
			result.update(status=STATUS_MANUAL_REVIEW, reason="Several rules match; a reviewer picks the product.")
	elif settings["no_match"] == NO_MATCH_DEFAULT_PRODUCT and settings["default_product"].get(loan_type):
		result.update(status=STATUS_LOAN_TYPE_DEFAULT, product=settings["default_product"][loan_type])
	else:
		result.update(status=STATUS_MANUAL_REVIEW, reason="No rule matches and this loan type has no default product.")

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
	"""The variables a rule condition can use, with their operators and options."""
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
