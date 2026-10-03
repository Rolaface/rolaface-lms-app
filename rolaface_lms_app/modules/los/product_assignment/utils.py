from typing import Any, Dict, List, Optional

import frappe
from frappe.utils import flt

from ..common import add_date_range, as_bool_flag, int_arg, json_contains, load_json, parse_id_list
from .constant import (
	CHANNEL_DOCTYPE,
	JOINERS,
	LEVEL_LOAN_TYPE,
	LIST_OPERATORS,
	LOAN_PRODUCT_DOCTYPE,
	NO_MATCH_DEFAULT_PRODUCT,
	NO_MATCH_OPTIONS,
	NUMBER_OPERATORS,
	RULE_NAME_MAX_LENGTH,
	SEVERAL_MATCH_OPTIONS,
	TREE_DOCTYPE,
	VARIABLES,
)


def load_references() -> Dict[str, Dict[str, str]]:
	return {
		"channels": dict(
			frappe.get_all(CHANNEL_DOCTYPE, filters={"is_active": 1}, fields=["name", "channel_name"], as_list=True)
		),
		"loan_types": dict(
			frappe.get_all(
				TREE_DOCTYPE,
				filters={"level": LEVEL_LOAN_TYPE, "is_active": 1},
				fields=["name", "node_name"],
				as_list=True,
			)
		),
		"products": dict(
			frappe.get_all(LOAN_PRODUCT_DOCTYPE, filters={"disabled": 0}, fields=["name", "product_name"], as_list=True)
		),
	}


def _prefix(index: Optional[int]) -> str:
	return f"Rule {index + 1}: " if index is not None else ""


def validate_settings(
	settings: Dict[str, Any], refs: Dict[str, Dict[str, str]], stored_defaults: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
	stored_defaults = stored_defaults or {}
	if settings.get("several_match") not in SEVERAL_MATCH_OPTIONS:
		raise frappe.ValidationError(f"several_match must be one of: {', '.join(SEVERAL_MATCH_OPTIONS)}.")
	if settings.get("no_match") not in NO_MATCH_OPTIONS:
		raise frappe.ValidationError(f"no_match must be one of: {', '.join(NO_MATCH_OPTIONS)}.")

	default_product = load_json(settings.get("default_product"), {}) or {}
	if not isinstance(default_product, dict):
		raise frappe.ValidationError("default_product must be an object of {loan type ID: product}.")

	cleaned = {}
	for loan_type, product in default_product.items():
		if not product:
			continue
		if loan_type not in refs["loan_types"] and loan_type not in stored_defaults:
			raise frappe.ValidationError(f"default_product: '{loan_type}' is not an active loan type.")
		if product not in refs["products"] and product != stored_defaults.get(loan_type):
			raise frappe.ValidationError(f"default_product: '{product}' is not an enabled loan product.")
		cleaned[loan_type] = product

	if settings["no_match"] == NO_MATCH_DEFAULT_PRODUCT and not cleaned:
		raise frappe.ValidationError("Choose a default product for at least one loan type, or switch to Manual Review.")

	settings["default_product"] = cleaned
	return settings


def validate_rule(
	data: Dict[str, Any],
	refs: Dict[str, Dict[str, str]],
	index: Optional[int] = None,
	current: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	prefix = _prefix(index)
	current = current or {}

	rule_name = str(data.get("rule_name") or "").strip()
	if len(rule_name) > RULE_NAME_MAX_LENGTH:
		raise frappe.ValidationError(f"{prefix}Rule Name cannot be longer than {RULE_NAME_MAX_LENGTH} characters.")

	sources = parse_id_list(data.get("sources"))
	if not sources:
		raise frappe.ValidationError(f"{prefix}Choose at least one source.")
	unknown = [s for s in sources if s not in refs["channels"] and s not in (current.get("sources") or [])]
	if unknown:
		raise frappe.ValidationError(f"{prefix}Not an active channel: {', '.join(unknown)}.")

	loan_types = parse_id_list(data.get("loan_types"))
	if not loan_types:
		raise frappe.ValidationError(f"{prefix}Choose at least one loan type.")
	unknown = [lt for lt in loan_types if lt not in refs["loan_types"] and lt not in (current.get("loan_types") or [])]
	if unknown:
		raise frappe.ValidationError(f"{prefix}Not an active loan type: {', '.join(unknown)}.")

	product = str(data.get("product") or "").strip()
	if not product:
		raise frappe.ValidationError(f"{prefix}Choose a product.")
	if product not in refs["products"] and product != current.get("product"):
		raise frappe.ValidationError(f"{prefix}'{product}' is not an enabled loan product.")

	return {
		"rule_name": rule_name or None,
		"sources": sources,
		"loan_types": loan_types,
		"condition": normalize_condition(data.get("condition"), prefix),
		"product": product,
	}


def normalize_condition(value, prefix: str = "") -> Optional[Dict[str, Any]]:
	condition = load_json(value, None)
	if not condition:
		return None
	if not isinstance(condition, dict):
		raise frappe.ValidationError(f"{prefix}condition must be an object.")

	groups = []
	for group in _objects(condition.get("groups"), f"{prefix}condition.groups"):
		clauses = [_normalize_clause(clause, prefix) for clause in _objects(group.get("clauses"), f"{prefix}clauses")]
		if clauses:
			groups.append(
				{
					"id": group.get("id"),
					"name": str(group.get("name") or "").strip(),
					"join": _joiner(group.get("join"), prefix),
					"clauses": clauses,
				}
			)

	if not groups:
		return None
	return {"join": _joiner(condition.get("join"), prefix), "groups": groups}


def _objects(value, label: str) -> List[Dict[str, Any]]:
	items = value or []
	if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
		raise frappe.ValidationError(f"{label} must be a list of objects.")
	return items


def _joiner(value, prefix: str) -> str:
	joiner = str(value or "AND").upper()
	if joiner not in JOINERS:
		raise frappe.ValidationError(f"{prefix}join must be AND or OR.")
	return joiner


def _normalize_clause(clause: Dict[str, Any], prefix: str) -> Dict[str, Any]:
	variable = VARIABLES.get(clause.get("variable"))
	if not variable:
		raise frappe.ValidationError(f"{prefix}Choose a variable for every condition.")

	operator = clause.get("operator") or "="
	allowed = NUMBER_OPERATORS if variable["numeric"] else LIST_OPERATORS
	if operator not in allowed:
		raise frappe.ValidationError(f"{prefix}'{operator}' cannot be used with {variable['label']}.")

	value = str(clause.get("value") if clause.get("value") is not None else "").strip()
	if not value:
		raise frappe.ValidationError(f"{prefix}Enter a value for {variable['label']}.")
	if variable["numeric"]:
		try:
			float(value)
		except ValueError:
			raise frappe.ValidationError(f"{prefix}{variable['label']} must be a number.")
	elif value not in variable["options"]:
		raise frappe.ValidationError(f"{prefix}{variable['label']} must be one of: {', '.join(variable['options'])}.")

	return {"id": clause.get("id"), "variable": clause["variable"], "operator": operator, "value": value}


def parse_rule_row(row: Dict[str, Any]) -> Dict[str, Any]:
	row["sources"] = load_json(row.get("sources"), []) or []
	row["loan_types"] = load_json(row.get("loan_types"), []) or []
	row["condition"] = load_json(row.get("condition"), None)
	return row


def find_shadowed(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	warnings = []
	for i, rule in enumerate(rules):
		if not rule.get("is_active", 1):
			continue
		for earlier in rules[:i]:
			if earlier.get("condition") or not earlier.get("is_active", 1):
				continue
			if set(rule["sources"]) <= set(earlier["sources"]) and set(rule["loan_types"]) <= set(earlier["loan_types"]):
				warnings.append(
					{
						"rule": rule.get("name"),
						"priority": i + 1,
						"message": f"Rule {i + 1} never matches: rule {rules.index(earlier) + 1} has no condition "
						"and already covers all its sources and loan types.",
					}
				)
				break
	return warnings


def build_rule_filters(args: Dict[str, Any]) -> Dict[str, Any]:
	filters = {}

	if args.get("product"):
		filters["product"] = args.get("product")
	if args.get("source"):
		filters["sources"] = json_contains("sources", args.get("source"))[1:]
	if args.get("loan_type"):
		filters["loan_types"] = json_contains("loan_types", args.get("loan_type"))[1:]

	is_active = as_bool_flag(args, "is_active")
	if is_active is not None:
		filters["is_active"] = is_active

	has_condition = as_bool_flag(args, "has_condition")
	if has_condition is not None:
		filters["condition"] = ["is", "set" if has_condition else "not set"]

	if args.get("rule_name"):
		filters["rule_name"] = ["like", f"%{str(args.get('rule_name')).strip()}%"]

	priority_from, priority_to = int_arg(args, "priority_from"), int_arg(args, "priority_to")
	if priority_from is not None and priority_to is not None:
		filters["priority"] = ["between", [priority_from, priority_to]]
	elif priority_from is not None:
		filters["priority"] = [">=", priority_from]
	elif priority_to is not None:
		filters["priority"] = ["<=", priority_to]

	ids = parse_id_list(args.get("ids"))
	if ids:
		filters["name"] = ["in", ids]

	add_date_range(filters, args)
	return filters


def evaluate_condition(condition: Optional[Dict[str, Any]], facts: Dict[str, Any]) -> bool:
	if not condition or not condition.get("groups"):
		return True
	results = [_evaluate_group(group, facts) for group in condition["groups"]]
	return all(results) if condition.get("join", "AND") == "AND" else any(results)


def _evaluate_group(group: Dict[str, Any], facts: Dict[str, Any]) -> bool:
	results = [_evaluate_clause(clause, facts) for clause in group.get("clauses") or []]
	return all(results) if group.get("join", "AND") == "AND" else any(results)


def _evaluate_clause(clause: Dict[str, Any], facts: Dict[str, Any]) -> bool:
	actual = facts.get(clause["variable"])
	if actual is None or actual == "":
		return False

	operator, expected = clause["operator"], clause["value"]
	if VARIABLES[clause["variable"]]["numeric"]:
		actual, expected = flt(actual), flt(expected)
	else:
		actual, expected = str(actual).strip().lower(), str(expected).strip().lower()

	return {
		"=": actual == expected,
		"<>": actual != expected,
		">": actual > expected,
		">=": actual >= expected,
		"<": actual < expected,
		"<=": actual <= expected,
	}[operator]
