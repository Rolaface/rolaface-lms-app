from typing import Any, Dict, List, Optional

import frappe
from frappe.utils import date_diff, flt, getdate, nowdate

from ..common import load_json

APPLICATION_DOCTYPE = "Custom LOS Loan Application"
TREE_DOCTYPE = "Custom LOS Loan Type Tree"
SECURITY_TYPE_DOCTYPE = "Loan Security Type"

ZAMBIA = "Zambia"
ZAMBIAN = "Zambian"
FOREIGN = "Foreign national"
NON_ZAMBIAN = "Non-Zambian"


def field_options(source, name: str) -> List[str]:
	if isinstance(source, (list, tuple)):
		return list(source)
	if source == "select":
		options = frappe.get_meta(APPLICATION_DOCTYPE).get_field(name).options or ""
		return [option for option in options.split("\n") if option]
	if source == "security_type":
		return frappe.get_all(SECURITY_TYPE_DOCTYPE, pluck="name", order_by="name asc")
	if source and source.startswith("tree:"):
		names = frappe.get_all(TREE_DOCTYPE, filters={"level": int(source[5:]), "is_active": 1}, pluck="node_name")
		return sorted(set(names))
	return []


def _years_since(value) -> Optional[int]:
	if not value:
		return None
	return date_diff(nowdate(), getdate(value)) // 365


def _lines(items) -> List[Dict[str, Any]]:
	return [
		{"source": str(item.get("source") or "").strip(), "monthly_amount": flt(item.get("monthly_amount"))}
		for item in items or []
		if flt(item.get("monthly_amount"))
	]


def application_facts(application: Dict[str, Any]) -> Dict[str, Any]:
	nodes = [application.get("loan_sub_type"), application.get("loan_purpose")]
	node_names = dict(frappe.get_all(TREE_DOCTYPE, filters={"name": ["in", [n for n in nodes if n]]}, fields=["name", "node_name"], as_list=True)) if any(nodes) else {}
	financials = load_json(application.get("financials"), {}) or {}
	income_lines, obligation_lines = _lines(financials.get("income")), _lines(financials.get("obligations"))
	income = sum(line["monthly_amount"] for line in income_lines) if income_lines else None
	obligations = sum(line["monthly_amount"] for line in obligation_lines) if (income_lines or obligation_lines) else None
	collaterals = [
		{"collateral_type": row.get("collateral_type"), "estimated_value": flt(row.get("estimated_value"))}
		for row in application.get("collaterals") or []
		if row.get("collateral_type")
	]
	nationality = application.get("nationality")
	debt_to_income = round((obligations or 0) / income * 100, 2) if income else None
	return {
		"customer_type": application.get("customer_type"),
		"loan_sub_type": node_names.get(application.get("loan_sub_type")),
		"loan_purpose": node_names.get(application.get("loan_purpose")),
		"requested_amount": application.get("requested_amount"),
		"loan_amount": application.get("requested_amount"),
		"tenure_months": application.get("tenure_months"),
		"loan_tenure": application.get("tenure_months"),
		"repayment_frequency": application.get("repayment_frequency"),
		"credit_score": application.get("credit_score") or None,
		"age": _years_since(application.get("date_of_birth")),
		"gender": application.get("gender"),
		"marital_status": application.get("marital_status"),
		"citizenship": (ZAMBIAN if nationality == ZAMBIA else FOREIGN) if nationality else None,
		"nationality": (ZAMBIAN if nationality == ZAMBIA else NON_ZAMBIAN) if nationality else None,
		"employment_status": application.get("employment_status"),
		"employment_type": application.get("employment_type"),
		"employer": application.get("employer_name"),
		"experience_years": application.get("experience_years"),
		"monthly_income": income,
		"monthly_obligations": obligations,
		"debt_to_income": debt_to_income,
		"dti": debt_to_income,
		"business_type": application.get("business_type"),
		"years_in_business": _years_since(application.get("established_date")),
		"director_count": len(application.get("directors") or []) or None,
		"collateral_type": [row["collateral_type"] for row in collaterals],
		"collateral_value": sum(row["estimated_value"] for row in collaterals),
		"income_lines": income_lines,
		"obligation_lines": obligation_lines,
		"collaterals": collaterals,
	}
