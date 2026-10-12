from typing import Any, Dict, List, Optional

import frappe
from frappe.utils import date_diff, flt, getdate, nowdate

from ..common import json_contains, load_json

APPLICATION_DOCTYPE = "Custom LOS Loan Application"
RULE_DOCTYPE = "Custom LOS Product Assignment Rule"
SETTINGS_DOCTYPE = "Custom LOS Product Assignment Settings"
DOCUMENT_SETUP_DOCTYPE = "Custom LOS Product Document Setup"
LOAN_PRODUCT_DOCTYPE = "Loan Product"
TREE_DOCTYPE = "Custom LOS Loan Type Tree"
SECURITY_TYPE_DOCTYPE = "Loan Security Type"

NO_MATCH_DEFAULT_PRODUCT = "Default Product"

STATUS_RULE_MATCHED = "Rule matched"
STATUS_LOAN_TYPE_DEFAULT = "Loan type default"
STATUS_MANUAL_REVIEW = "Manual review"
STATUS_CONFLICT = "Conflict"

ZAMBIAN = "Zambian"
FOREIGN = "Foreign national"

VARIABLES = {
	"customer_type": {"label": "Customer type", "options": "select"},
	"loan_sub_type": {"label": "Loan sub-type", "options": "tree:2"},
	"loan_purpose": {"label": "Loan purpose", "options": "tree:3"},
	"requested_amount": {"label": "Requested amount", "numeric": True},
	"tenure_months": {"label": "Tenure (months)", "numeric": True},
	"repayment_frequency": {"label": "Repayment frequency", "options": "select"},
	"credit_score": {"label": "Credit score", "numeric": True},
	"age": {"label": "Applicant age", "numeric": True},
	"gender": {"label": "Gender", "options": "select"},
	"marital_status": {"label": "Marital status", "options": "select"},
	"citizenship": {"label": "Citizenship", "options": [ZAMBIAN, FOREIGN]},
	"employment_status": {"label": "Employment status", "options": "select", "applies_to": "Individual"},
	"employment_type": {"label": "Employment type", "options": "select", "applies_to": "Individual"},
	"experience_years": {"label": "Work experience (years)", "numeric": True, "applies_to": "Individual"},
	"monthly_income": {"label": "Monthly income", "numeric": True, "applies_to": "Individual"},
	"monthly_obligations": {"label": "Monthly obligations", "numeric": True, "applies_to": "Individual"},
	"debt_to_income": {"label": "Debt-to-income (%)", "numeric": True, "applies_to": "Individual"},
	"business_type": {"label": "Business type", "options": "select", "applies_to": "Business"},
	"years_in_business": {"label": "Years in business", "numeric": True, "applies_to": "Business"},
	"director_count": {"label": "Number of directors", "numeric": True, "applies_to": "Business"},
	"collateral_type": {"label": "Collateral type", "options": "security_type"},
	"collateral_value": {"label": "Total collateral value", "numeric": True},
}


def variable_options(spec: Dict[str, Any], name: str) -> List[str]:
	source = spec.get("options")
	if isinstance(source, list):
		return source
	if source == "select":
		options = frappe.get_meta(APPLICATION_DOCTYPE).get_field(name).options or ""
		return [option for option in options.split("\n") if option]
	if source == "security_type":
		return frappe.get_all(SECURITY_TYPE_DOCTYPE, pluck="name", order_by="name asc")
	if source and source.startswith("tree:"):
		names = frappe.get_all(TREE_DOCTYPE, filters={"level": int(source[5:]), "is_active": 1}, pluck="node_name")
		return sorted(set(names))
	return []


def condition_variables() -> Dict[str, Dict[str, Any]]:
	return {
		name: {
			"label": spec["label"],
			"numeric": bool(spec.get("numeric")),
			"options": [] if spec.get("numeric") else variable_options(spec, name),
			"applies_to": spec.get("applies_to"),
		}
		for name, spec in VARIABLES.items()
	}


def _years_since(value) -> Optional[int]:
	if not value:
		return None
	return date_diff(nowdate(), getdate(value)) // 365


def _total(items) -> float:
	return sum(flt(item.get("monthly_amount")) for item in items or [])


def application_facts(application: Dict[str, Any]) -> Dict[str, Any]:
	nodes = [application.get("loan_sub_type"), application.get("loan_purpose")]
	node_names = dict(frappe.get_all(TREE_DOCTYPE, filters={"name": ["in", [n for n in nodes if n]]}, fields=["name", "node_name"], as_list=True)) if any(nodes) else {}
	financials = load_json(application.get("financials"), {}) or {}
	individual = application.get("applicant_type") == "Individual"
	income = _total(financials.get("income")) if individual else None
	obligations = _total(financials.get("obligations")) if individual else None
	collaterals = application.get("collaterals") or []
	nationality = application.get("nationality")
	return {
		"customer_type": application.get("customer_type"),
		"loan_sub_type": node_names.get(application.get("loan_sub_type")),
		"loan_purpose": node_names.get(application.get("loan_purpose")),
		"requested_amount": application.get("requested_amount"),
		"tenure_months": application.get("tenure_months"),
		"repayment_frequency": application.get("repayment_frequency"),
		"credit_score": application.get("credit_score") or None,
		"age": _years_since(application.get("date_of_birth")),
		"gender": application.get("gender"),
		"marital_status": application.get("marital_status"),
		"citizenship": (ZAMBIAN if nationality == "Zambia" else FOREIGN) if nationality else None,
		"employment_status": application.get("employment_status"),
		"employment_type": application.get("employment_type"),
		"experience_years": application.get("experience_years"),
		"monthly_income": income,
		"monthly_obligations": obligations,
		"debt_to_income": round((obligations or 0) / income * 100, 2) if income else None,
		"business_type": application.get("business_type"),
		"years_in_business": _years_since(application.get("established_date")),
		"director_count": len(application.get("directors") or []) or None,
		"collateral_type": [row.get("collateral_type") for row in collaterals if row.get("collateral_type")],
		"collateral_value": sum(flt(row.get("estimated_value")) for row in collaterals),
	}


def evaluate_condition(condition: Optional[Dict[str, Any]], facts: Dict[str, Any]) -> bool:
	if not condition or not condition.get("groups"):
		return True
	results = [_evaluate_group(group, facts) for group in condition["groups"]]
	return all(results) if condition.get("join", "AND") == "AND" else any(results)


def _evaluate_group(group: Dict[str, Any], facts: Dict[str, Any]) -> bool:
	results = [_evaluate_clause(clause, facts) for clause in group.get("clauses") or []]
	return all(results) if group.get("join", "AND") == "AND" else any(results)


def _evaluate_clause(clause: Dict[str, Any], facts: Dict[str, Any]) -> bool:
	spec = VARIABLES.get(clause["variable"])
	actual = facts.get(clause["variable"])
	operator, expected = clause["operator"], clause["value"]
	if spec is None or actual is None or actual == "":
		return False
	if isinstance(actual, list):
		values = [str(value).strip().lower() for value in actual]
		hit = str(expected).strip().lower() in values
		return hit if operator == "=" else not hit
	if operator == "between":
		return flt(expected) <= flt(actual) <= flt(clause["value2"])
	if spec.get("numeric"):
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


def read_settings() -> Dict[str, Any]:
	stored = frappe.db.get_singles_dict(SETTINGS_DOCTYPE)
	meta = frappe.get_meta(SETTINGS_DOCTYPE)
	return {
		"several_match": stored.get("several_match") or meta.get_field("several_match").default,
		"no_match": stored.get("no_match") or meta.get_field("no_match").default,
		"default_product": load_json(stored.get("default_product"), {}) or {},
	}


def match_product(source: str, loan_type: str, facts: Dict[str, Any]) -> Dict[str, Any]:
	settings = read_settings()
	candidates = frappe.get_all(
		RULE_DOCTYPE,
		filters=[["is_active", "=", 1], json_contains("sources", source), json_contains("loan_types", loan_type)],
		fields=["product", "product_name", "sources", "loan_types", "condition"],
		limit_page_length=0,
	)
	products = {c.product for c in candidates} | set(settings["default_product"].values())
	enabled = set(frappe.get_all(LOAN_PRODUCT_DOCTYPE, filters={"disabled": 0, "name": ["in", list(products)]}, pluck="name")) if products else set()
	matches = [
		rule
		for rule in candidates
		if source in (load_json(rule.sources, []) or [])
		and loan_type in (load_json(rule.loan_types, []) or [])
		and rule.product in enabled
		and evaluate_condition(load_json(rule.condition, None), facts)
	]
	default_product = settings["default_product"].get(loan_type)

	result = {"source": source, "loan_type": loan_type, "product": None, "reason": None}
	if len(matches) == 1:
		result.update(status=STATUS_RULE_MATCHED, product=matches[0].product)
	elif matches:
		result.update(
			status=STATUS_CONFLICT,
			reason="More than one product's rule matches. Change the rules so only one product matches.",
		)
	elif settings["no_match"] == NO_MATCH_DEFAULT_PRODUCT and default_product in enabled:
		result.update(status=STATUS_LOAN_TYPE_DEFAULT, product=default_product)
	else:
		result.update(status=STATUS_MANUAL_REVIEW, reason="No rule matches and this loan type has no enabled default product.")
	result["matched_rules"] = [{"product": r.product, "product_name": r.product_name} for r in matches]
	result["product_name"] = frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, result["product"], "product_name") if result["product"] else None
	return result


def assign_product(application: Dict[str, Any]) -> Dict[str, Any]:
	if not application.get("loan_type"):
		raise frappe.ValidationError("loan_type is required.")
	result = match_product(application.get("channel") or "Branch", application["loan_type"], application_facts(application))
	product = result["product"]
	terms = frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, product, ["rate_of_interest", "maximum_loan_amount"], as_dict=True) if product else None
	setup = frappe.db.get_value(DOCUMENT_SETUP_DOCTYPE, {"loan_product": product}, "documents") if product else None
	result.update(
		rate_of_interest=flt(terms.rate_of_interest) if terms else None,
		maximum_loan_amount=flt(terms.maximum_loan_amount) if terms else None,
		documents=load_json(setup, None),
	)
	return result
