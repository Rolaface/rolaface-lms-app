from typing import Any, Dict, List

import frappe
from frappe.utils import add_days, add_months, add_years, getdate, nowdate

from ..common import load_json
from .constant import (
	ACTIONS,
	DATE_UNITS,
	FIELDS,
	FIRST_VERSION,
	LOGICS,
	OPERATORS,
	SEVERITIES,
	VERDICT_ELIGIBLE,
	VERDICT_NOT_ELIGIBLE,
	VERDICT_REVIEW,
	VERDICT_WARNINGS,
)

# ---------------------------------------------------------------- Rule groups
# A draft may hold unfinished rules (Save Draft). Activation needs every rule complete (complete=True).


def normalize_groups(value, complete: bool = False) -> List[Dict[str, Any]]:
	groups = load_json(value, [])
	if not isinstance(groups, list):
		raise frappe.ValidationError("groups must be a list.")
	if complete and not groups:
		raise frappe.ValidationError("Add at least one rule group.")
	return [_normalize_group(group, index, complete) for index, group in enumerate(groups)]


def _normalize_group(group, index: int, complete: bool) -> Dict[str, Any]:
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
		"rules": [_normalize_rule(rule, f'"{name}", rule {i + 1}', complete) for i, rule in enumerate(rules)],
	}


def _normalize_rule(rule, where: str, complete: bool) -> Dict[str, Any]:
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

	field = FIELDS.get(result["field"]) if result["field"] else None
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
	"""Checks and cleans value / value2 / values / date_unit for the field type and operator."""
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


# ---------------------------------------------------------------- Versions


def next_version(versions: List[str]) -> str:
	"""One step (0.1) above the highest version so far. Tenths are counted as integers to avoid float drift."""
	published = [_tenths(v) for v in versions if v]
	if not published:
		return FIRST_VERSION
	nxt = max(published) + 1
	return f"{nxt // 10}.{nxt % 10}"


def _tenths(version: str) -> int:
	major, _, minor = str(version).partition(".")
	return int(major or 0) * 10 + int((minor or "0")[:1])


def clean_ruleset_name(value, max_length: int) -> str:
	name = str(value or "").strip()
	if not name:
		raise frappe.ValidationError("Rule Set Name is required.")
	if len(name) > max_length:
		raise frappe.ValidationError(f"Rule Set Name cannot be longer than {max_length} characters.")
	return name


# ---------------------------------------------------------------- Evaluation (Test tab, later the loan application)
# A rule gives True (met), False (not met) or None (no value supplied for its field, or the rule is unfinished).
# Only failures inside a failed group count towards the verdict.


def evaluate(groups: List[Dict[str, Any]], facts: Dict[str, Any]) -> Dict[str, Any]:
	group_results, failed = [], []
	for group in groups:
		rules = [_rule_result(rule, facts) for rule in group["rules"] if not rule.get("disabled")]
		checked = [r["passed"] for r in rules if r["passed"] is not None]
		if not checked:
			passed = None
		elif group["logic"] == "ALL":
			passed = all(checked)
		else:
			passed = any(checked)

		if passed is False:
			failed += [{**r, "group": group["name"]} for r in rules if r["passed"] is False]
		group_results.append({"id": group["id"], "name": group["name"], "logic": group["logic"], "passed": passed, "rules": rules})

	return {"verdict": _verdict(failed), "failed": failed, "groups": group_results}


def _verdict(failed: List[Dict[str, Any]]) -> str:
	severities = {r["severity"] for r in failed}
	if "Blocking" in severities:
		return VERDICT_NOT_ELIGIBLE
	if "Review" in severities:
		return VERDICT_REVIEW
	if "Warning" in severities:
		return VERDICT_WARNINGS
	return VERDICT_ELIGIBLE


def _rule_result(rule: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
	field = FIELDS.get(rule.get("field"))
	actual = facts.get(rule.get("field")) if field else None
	result = {
		"id": rule["id"],
		"field": rule.get("field"),
		"label": field["label"] if field else None,
		"operator": rule.get("operator"),
		"severity": rule["severity"],
		"action": rule["action"],
		"actual": actual,
		"passed": None,
	}
	if field and not _empty(actual) and _is_complete(rule):
		result["passed"] = _compare(field["type"], rule, actual)
	return result


def _is_complete(rule: Dict[str, Any]) -> bool:
	if rule["operator"] in ("in", "not_in"):
		return bool(rule.get("values"))
	if rule["operator"] == "between":
		return rule.get("value") is not None and rule.get("value2") is not None
	return rule.get("value") is not None


def _compare(kind: str, rule: Dict[str, Any], actual) -> bool:
	"""Compares the applicant's value with the rule. The rule's values are already clean (see normalize_groups)."""
	operator, where = rule["operator"], f"facts.{rule['field']}"
	value, value2 = rule.get("value"), rule.get("value2")

	if kind == "numeric":
		actual = _number(actual, where, complete=True)
	elif kind == "boolean":
		actual = _boolean(actual, where, complete=True)
	elif kind == "date":
		actual = _date(actual, where, complete=True)
	else:  # text and dropdown: compared without case
		actual = str(actual).strip().lower()
		value = str(value).strip().lower() if value is not None else None

	if operator == "equals":
		return actual == value
	if operator == "not_equals":
		return actual != value
	if operator in ("greater_than", "after"):
		return actual > value
	if operator == "greater_than_or_equal":
		return actual >= value
	if operator in ("less_than", "before"):
		return actual < value
	if operator == "less_than_or_equal":
		return actual <= value
	if operator == "between":
		return value <= actual <= value2
	if operator in ("in", "not_in"):
		found = actual in [str(v).strip().lower() for v in rule["values"]]
		return found if operator == "in" else not found
	if operator == "contains":
		return value in actual
	if operator == "starts_with":
		return actual.startswith(value)
	if operator == "older_than":
		return getdate(actual) <= _ago(rule["value"], rule.get("date_unit") or "months")
	raise frappe.ValidationError(f"Operator '{operator}' is not supported.")


def _ago(amount, unit: str):
	"""The date `amount` days, months or years before today."""
	amount = int(amount)
	if unit == "days":
		return getdate(add_days(nowdate(), -amount))
	if unit == "years":
		return getdate(add_years(nowdate(), -amount))
	return getdate(add_months(nowdate(), -amount))
