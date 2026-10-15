from typing import Any, Dict, List

from frappe.utils import add_days, add_months, add_years, flt, getdate, nowdate

from .facts import NON_ZAMBIAN, ZAMBIAN, field_options

VERDICT_ELIGIBLE = "Eligible"
VERDICT_WARNINGS = "Eligible with Warnings"
VERDICT_REVIEW = "Manual Review"
VERDICT_NOT_ELIGIBLE = "Not Eligible"
VERDICT_ORDER = (VERDICT_ELIGIBLE, VERDICT_WARNINGS, VERDICT_REVIEW, VERDICT_NOT_ELIGIBLE)

FIELDS = {
	"age": {"label": "Applicant Age", "category": "Applicant", "type": "numeric", "unit": "years"},
	"gender": {"label": "Gender", "category": "Applicant", "type": "dropdown", "options": "select"},
	"marital_status": {"label": "Marital Status", "category": "Applicant", "type": "dropdown", "options": "select"},
	"nationality": {"label": "Nationality", "category": "Applicant", "type": "dropdown", "options": [ZAMBIAN, NON_ZAMBIAN]},
	"customer_type": {"label": "Customer Type", "category": "Applicant", "type": "dropdown", "options": "select"},
	"employment_status": {"label": "Employment Status", "category": "Employment", "type": "dropdown", "options": "select"},
	"employment_type": {"label": "Employment Type", "category": "Employment", "type": "dropdown", "options": "select"},
	"employer": {"label": "Employer", "category": "Employment", "type": "text"},
	"experience_years": {"label": "Work Experience", "category": "Employment", "type": "numeric", "unit": "years"},
	"monthly_income": {"label": "Monthly Income", "category": "Income & Credit", "type": "numeric", "unit": "ZMW"},
	"monthly_obligations": {"label": "Monthly Obligations", "category": "Income & Credit", "type": "numeric", "unit": "ZMW"},
	"dti": {"label": "Debt-to-Income Ratio", "category": "Income & Credit", "type": "numeric", "unit": "%"},
	"credit_score": {"label": "Credit Score", "category": "Income & Credit", "type": "numeric", "unit": "pts"},
	"loan_amount": {"label": "Loan Amount", "category": "Loan", "type": "numeric", "unit": "ZMW"},
	"loan_tenure": {"label": "Loan Tenure", "category": "Loan", "type": "numeric", "unit": "months"},
	"loan_sub_type": {"label": "Loan Sub-type", "category": "Loan", "type": "dropdown", "options": "tree:2"},
	"loan_purpose": {"label": "Loan Purpose", "category": "Loan", "type": "dropdown", "options": "tree:3"},
	"repayment_frequency": {"label": "Repayment Frequency", "category": "Loan", "type": "dropdown", "options": "select"},
	"business_type": {"label": "Business Type", "category": "Business", "type": "dropdown", "options": "select"},
	"years_in_business": {"label": "Years in Business", "category": "Business", "type": "numeric", "unit": "years"},
	"collateral_type": {"label": "Collateral Type", "category": "Collateral", "type": "dropdown", "options": "security_type"},
	"collateral_value": {"label": "Total Collateral Value", "category": "Collateral", "type": "numeric", "unit": "ZMW"},
}


def prescreening_fields() -> Dict[str, Dict[str, Any]]:
	fields = {}
	for field_id, spec in FIELDS.items():
		field = {key: value for key, value in spec.items() if key != "options"}
		if "options" in spec:
			field["options"] = field_options(spec["options"], field_id)
		fields[field_id] = field
	return fields


def worst_verdict(*verdicts: str) -> str:
	return max((v for v in verdicts if v), key=VERDICT_ORDER.index, default=VERDICT_ELIGIBLE)


def run_prescreening(groups: List[Dict[str, Any]], facts: Dict[str, Any]) -> Dict[str, Any]:
	group_results, failed = [], []
	for group in groups:
		rules = [_rule_result(rule, facts) for rule in group.get("rules") or [] if not rule.get("disabled") and rule.get("field")]
		if not rules:
			passed = None
		elif group.get("logic") == "ANY":
			passed = any(r["passed"] for r in rules)
		else:
			passed = all(r["passed"] for r in rules)

		if passed is False:
			failed += [{**r, "group": group.get("name")} for r in rules if not r["passed"]]
		group_results.append({"id": group.get("id"), "name": group.get("name"), "logic": group.get("logic"), "passed": passed, "rules": rules})

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
	missing = field is None or actual is None or actual == "" or actual == []
	return {
		"id": rule.get("id"),
		"field": rule.get("field"),
		"label": field["label"] if field else rule.get("field"),
		"operator": rule.get("operator"),
		"value": rule.get("value"),
		"value2": rule.get("value2"),
		"values": rule.get("values"),
		"severity": rule.get("severity"),
		"action": rule.get("action"),
		"actual": actual,
		"missing": missing,
		"passed": False if missing else _compare(field["type"], rule, actual),
	}


def _compare(kind: str, rule: Dict[str, Any], actual) -> bool:
	operator = rule.get("operator")
	if isinstance(actual, (list, tuple)):
		values = [str(v).strip().lower() for v in (rule.get("values") if operator in ("in", "not_in") else [rule.get("value")]) or []]
		hit = any(str(a).strip().lower() in values for a in actual)
		return hit if operator in ("equals", "in") else not hit

	value, value2 = rule.get("value"), rule.get("value2")
	if kind == "numeric":
		actual, value, value2 = flt(actual), flt(value), flt(value2)
	elif kind == "date":
		actual = getdate(actual)
		value = getdate(value) if value and operator != "older_than" else value
		value2 = getdate(value2) if value2 else value2
	elif kind == "boolean":
		actual = actual in (True, 1, "1", "true", "Yes")
		value = value in (True, 1, "1", "true", "Yes")
	else:
		actual = str(actual).strip().lower()
		value = str(value).strip().lower() if value is not None else ""

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
		found = actual in [str(v).strip().lower() for v in rule.get("values") or []]
		return found if operator == "in" else not found
	if operator == "contains":
		return value in actual
	if operator == "starts_with":
		return actual.startswith(value)
	if operator == "older_than":
		return actual <= _ago(value, rule.get("date_unit") or "months")
	return False


def _ago(amount, unit: str):
	amount = int(flt(amount))
	if unit == "days":
		return getdate(add_days(nowdate(), -amount))
	if unit == "years":
		return getdate(add_years(nowdate(), -amount))
	return getdate(add_months(nowdate(), -amount))
