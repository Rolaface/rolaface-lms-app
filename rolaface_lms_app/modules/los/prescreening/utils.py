from typing import Any, Dict, List

import frappe
from frappe.utils import getdate

from ..common import load_json
from ..engine.prescreening import prescreening_fields
from .constant import ACTIONS, DATE_UNITS, LOGICS, OPERATORS, SEVERITIES


def normalize_groups(value, complete: bool = False) -> List[Dict[str, Any]]:
	groups = load_json(value, [])
	if not isinstance(groups, list):
		raise frappe.ValidationError("groups must be a list.")
	if complete and not groups:
		raise frappe.ValidationError("Add at least one rule group.")
	fields = prescreening_fields()
	return [_normalize_group(group, index, complete, fields) for index, group in enumerate(groups)]


def _normalize_group(group, index: int, complete: bool, fields: Dict[str, Any]) -> Dict[str, Any]:
	if not isinstance(group, dict):
		raise frappe.ValidationError(f"Group {index + 1} must be an object.")
	name = str(group.get("name") or "").strip() or f"Group {index + 1}"
	logic = str(group.get("logic") or "ALL").upper()
	if logic not in LOGICS:
		raise frappe.ValidationError(f'"{name}": logic must be ALL or ANY.')

	rules = group.get("rules") or []
	if not isinstance(rules, list):
		raise frappe.ValidationError(f'"{name}": rules must be a list.')
	if complete and not rules:
		raise frappe.ValidationError(f'"{name}" has no rules configured.')

	return {
		"id": group.get("id") or frappe.generate_hash(length=8),
		"name": name,
		"logic": logic,
		"rules": [_normalize_rule(rule, f'"{name}", rule {i + 1}', complete, fields) for i, rule in enumerate(rules)],
	}


def _normalize_rule(rule, where: str, complete: bool, fields: Dict[str, Any]) -> Dict[str, Any]:
	if not isinstance(rule, dict):
		raise frappe.ValidationError(f"{where} must be an object.")

	severity = rule.get("severity") or "Blocking"
	if severity not in SEVERITIES:
		raise frappe.ValidationError(f"{where}: severity must be one of {', '.join(SEVERITIES)}.")
	action = rule.get("action") or SEVERITIES[severity]
	if action not in ACTIONS:
		raise frappe.ValidationError(f"{where}: action must be one of {', '.join(ACTIONS)}.")

	result = {
		"id": rule.get("id") or frappe.generate_hash(length=8),
		"field": rule.get("field") or None,
		"operator": rule.get("operator") or None,
		"severity": severity,
		"action": action,
		"disabled": bool(rule.get("disabled")),
	}

	field = fields.get(result["field"]) if result["field"] else None
	if result["field"] and not field:
		raise frappe.ValidationError(f"{where}: unknown field '{result['field']}'.")
	if not field:
		if complete:
			raise frappe.ValidationError(f"{where}: choose a field.")
		return result

	where = f"{where} ({field['label']})"
	allowed = OPERATORS[field["type"]]
	if result["operator"] is None:
		result["operator"] = allowed[0]
	if result["operator"] not in allowed:
		raise frappe.ValidationError(f"{where}: operator must be one of {', '.join(allowed)}.")

	result.update(_values(rule, field, result["operator"], where, complete))
	return result


def _values(rule: Dict[str, Any], field: Dict[str, Any], operator: str, where: str, complete: bool) -> Dict[str, Any]:
	kind = field["type"]

	if operator in ("in", "not_in"):
		values = [str(v).strip() for v in (rule.get("values") or []) if str(v).strip()]
		if field.get("options"):
			unknown = [v for v in values if v not in field["options"]]
			if unknown:
				raise frappe.ValidationError(f"{where}: {', '.join(unknown)} not allowed. Use {', '.join(field['options'])}.")
		if complete and not values:
			raise frappe.ValidationError(f"{where}: choose at least one value.")
		return {"values": values}

	if operator == "older_than":
		date_unit = rule.get("date_unit") or "months"
		if date_unit not in DATE_UNITS:
			raise frappe.ValidationError(f"{where}: date_unit must be one of {', '.join(DATE_UNITS)}.")
		return {"value": _number(rule.get("value"), where, complete, positive=True), "date_unit": date_unit}

	convert = {"numeric": _number, "date": _date, "boolean": _boolean}.get(kind, _text)
	cleaned = {"value": convert(rule.get("value"), where, complete)}
	if kind == "dropdown" and cleaned["value"] is not None and cleaned["value"] not in field["options"]:
		raise frappe.ValidationError(f"{where}: must be one of {', '.join(field['options'])}.")

	if operator == "between":
		cleaned["value2"] = convert(rule.get("value2"), where, complete)
		low, high = cleaned["value"], cleaned["value2"]
		if low is not None and high is not None and high < low:
			raise frappe.ValidationError(f"{where}: the second value must not be lower than the first.")
	return cleaned


def _empty(value) -> bool:
	return value is None or (isinstance(value, str) and not value.strip())


def _missing(where: str, complete: bool):
	if complete:
		raise frappe.ValidationError(f"{where}: enter a value.")
	return None


def _number(value, where: str, complete: bool, positive: bool = False):
	if _empty(value):
		return _missing(where, complete)
	try:
		number = float(value)
	except (TypeError, ValueError):
		raise frappe.ValidationError(f"{where}: must be a number.")
	if positive and number <= 0:
		raise frappe.ValidationError(f"{where}: must be more than 0.")
	return int(number) if number.is_integer() else number


def _date(value, where: str, complete: bool):
	if _empty(value):
		return _missing(where, complete)
	try:
		return getdate(value).isoformat()
	except Exception:
		raise frappe.ValidationError(f"{where}: must be a date (YYYY-MM-DD).")


def _boolean(value, where: str, complete: bool):
	if value is None or value == "":
		return _missing(where, complete)
	if value in (True, 1, "1", "true", "Yes"):
		return True
	if value in (False, 0, "0", "false", "No"):
		return False
	raise frappe.ValidationError(f"{where}: must be true or false.")


def _text(value, where: str, complete: bool):
	if _empty(value):
		return _missing(where, complete)
	return str(value).strip()


def count_rules(groups) -> int:
	return sum(len(group.get("rules") or []) for group in load_json(groups, []) or [])


def clean_ruleset_name(value, max_length: int) -> str:
	name = str(value or "").strip()
	if not name:
		raise frappe.ValidationError("Rule Set Name is required.")
	if len(name) > max_length:
		raise frappe.ValidationError(f"Rule Set Name cannot be longer than {max_length} characters.")
	return name
