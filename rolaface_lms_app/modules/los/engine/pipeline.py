from typing import Any, Dict, Optional

import frappe
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from ..common import dump_json, load_json
from ..loan_application.constant import CREDIT_SCORE_RANGE
from ..loan_application.utils import parse_application
from .eligibility import run_eligibility
from .facts import APPLICATION_DOCTYPE, application_facts
from .prescreening import VERDICT_ELIGIBLE, VERDICT_NOT_ELIGIBLE, VERDICT_REVIEW, VERDICT_WARNINGS, run_prescreening, worst_verdict

PRESCREENING_DOCTYPE = "Custom LOS Prescreening Ruleset"
ELIGIBILITY_DOCTYPE = "Custom LOS Eligibility Rule"
LOAN_PRODUCT_DOCTYPE = "Loan Product"
ACTIVE = "Active"
PRESCREENING_STATE = "Pre-Screening"

TRIGGER_WORKFLOW = "Workflow"
TRIGGER_OFFICER = "Officer"
SAVEPOINT = "los_engine"

STAGE_STATUS = {VERDICT_ELIGIBLE: "Pass", VERDICT_WARNINGS: "Warning", VERDICT_REVIEW: "Review", VERDICT_NOT_ELIGIBLE: "Fail"}
APPROVED = "Approved"

ELIGIBILITY_SECTIONS = ("income_sources", "obligation_sources", "credit_bands", "collateral_items", "formula_params", "hard_stops", "manual_reviews")


def active_version(doctype: str, loan_product: Optional[str], fields) -> Optional[Dict[str, Any]]:
	if not loan_product:
		return None
	today = getdate(nowdate())
	for row in frappe.get_all(doctype, filters={"loan_product": loan_product, "status": ACTIVE}, fields=["name", "version", "effective_from", "effective_to", *fields], order_by="creation desc"):
		if (not row.effective_from or getdate(row.effective_from) <= today) and (not row.effective_to or getdate(row.effective_to) >= today):
			return row
	return None


def _product(loan_product: Optional[str]) -> Dict[str, Any]:
	if not loan_product:
		return {}
	return frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, loan_product, ["name", "product_name", "rate_of_interest", "maximum_loan_amount"], as_dict=True) or {}


def prescreen(facts: Dict[str, Any], loan_product: Optional[str]) -> Dict[str, Any]:
	ruleset = active_version(PRESCREENING_DOCTYPE, loan_product, ["groups"])
	if not ruleset:
		reason = f"No active pre-screening rules for {loan_product}." if loan_product else "No loan product is assigned."
		return {"ruleset": None, "version": None, "verdict": VERDICT_REVIEW, "reason": reason, "failed": [], "groups": []}
	result = run_prescreening(load_json(ruleset.groups, []) or [], facts)
	return {"ruleset": ruleset.name, "version": ruleset.version, "reason": None, **result}


def check_eligibility(facts: Dict[str, Any], loan_product: Optional[str], product: Dict[str, Any]) -> Dict[str, Any]:
	rule = active_version(ELIGIBILITY_DOCTYPE, loan_product, ELIGIBILITY_SECTIONS)
	if not rule:
		reason = f"No active eligibility rule for {loan_product}." if loan_product else "No loan product is assigned."
		return {"rule": None, "version": None, "decision": VERDICT_REVIEW, "eligible_amount": None, "reasons": [reason]}
	sections = {section: load_json(rule.get(section), None) for section in ELIGIBILITY_SECTIONS}
	return {"rule": rule.name, "version": rule.version, **run_eligibility(sections, facts, product)}


def eligibility_policy(loan_product: Optional[str], product: Dict[str, Any]) -> Dict[str, Any]:
	rule = active_version(ELIGIBILITY_DOCTYPE, loan_product, ["formula_params"])
	params = (load_json(rule.formula_params, {}) or {}) if rule else {}
	return {
		"rule": rule.name if rule else None,
		"version": rule.version if rule else None,
		"max_dti_ratio": flt(params.get("max_dti_ratio")),
		"max_emi_ratio": flt(params.get("max_emi_ratio")),
		"rate_of_interest": flt(product.get("rate_of_interest")),
	}


def clean_overrides(overrides) -> Dict[str, Any]:
	overrides = load_json(overrides, {}) or {}
	if not isinstance(overrides, dict):
		raise frappe.ValidationError("overrides must be an object.")
	cleaned = {}
	if overrides.get("credit_score") not in (None, ""):
		score = cint(overrides["credit_score"])
		if not CREDIT_SCORE_RANGE[0] <= score <= CREDIT_SCORE_RANGE[1]:
			raise frappe.ValidationError(f"credit_score must be between {CREDIT_SCORE_RANGE[0]} and {CREDIT_SCORE_RANGE[1]}.")
		cleaned["credit_score"] = score
	if overrides.get("requested_amount") not in (None, ""):
		if flt(overrides["requested_amount"]) <= 0:
			raise frappe.ValidationError("requested_amount must be more than 0.")
		cleaned["requested_amount"] = flt(overrides["requested_amount"])
	for key in ("income", "obligations"):
		if key in overrides:
			lines = overrides[key] or []
			if not isinstance(lines, list) or not all(isinstance(line, dict) for line in lines):
				raise frappe.ValidationError(f"{key} must be a list of {{source, monthly_amount}}.")
			if any(flt(line.get("monthly_amount")) < 0 for line in lines):
				raise frappe.ValidationError(f"{key}: monthly_amount cannot be negative.")
			cleaned[key] = [{"source": str(line.get("source") or "").strip(), "monthly_amount": flt(line.get("monthly_amount"))} for line in lines]
	return cleaned


def apply_overrides(application: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
	application = dict(application)
	for key in ("credit_score", "requested_amount"):
		if key in overrides:
			application[key] = overrides[key]
	if "income" in overrides or "obligations" in overrides:
		financials = dict(load_json(application.get("financials"), {}) or {})
		for key in ("income", "obligations"):
			if key in overrides:
				financials[key] = overrides[key]
		application["financials"] = financials
	return application


def evaluate(application: Dict[str, Any]) -> Dict[str, Any]:
	loan_product = application.get("loan_product")
	product = _product(loan_product)
	facts = application_facts(application)
	prescreening = prescreen(facts, loan_product)
	if prescreening["verdict"] == VERDICT_NOT_ELIGIBLE:
		eligibility = {"skipped": True, "reasons": ["Pre-screening is Not Eligible."], **eligibility_policy(loan_product, product)}
		verdict = VERDICT_NOT_ELIGIBLE
	else:
		eligibility = check_eligibility(facts, loan_product, product)
		verdict = worst_verdict(prescreening["verdict"], eligibility["decision"])
	return {
		"verdict": verdict,
		"loan_product": loan_product,
		"product_name": product.get("product_name"),
		"requested_amount": flt(application.get("requested_amount")),
		"eligible_amount": 0.0 if verdict == VERDICT_NOT_ELIGIBLE else eligibility.get("eligible_amount"),
		"prescreening": prescreening,
		"eligibility": eligibility,
	}


def load_application(application_id: str) -> Dict[str, Any]:
	if not application_id or not frappe.db.exists(APPLICATION_DOCTYPE, application_id):
		raise frappe.DoesNotExistError(f"Loan application '{application_id}' does not exist.")
	return parse_application(frappe.get_doc(APPLICATION_DOCTYPE, application_id))


def _check_approval(result: Dict[str, Any]):
	if result["verdict"] == VERDICT_NOT_ELIGIBLE:
		raise frappe.ValidationError("A Fail result cannot be approved. Reject the application from the workflow menu.")
	eligibility = result["eligibility"]
	if result["verdict"] != VERDICT_REVIEW and not eligibility.get("meets_request"):
		raise frappe.ValidationError("The requested amount is above the eligible amount. Use the eligible amount before approving.")


def evaluate_application(application_id: str, overrides=None, save: bool = False, trigger: str = TRIGGER_OFFICER, approve: bool = False) -> Dict[str, Any]:
	application = load_application(application_id)
	if approve and overrides is None:
		overrides = ((load_json(application.get("prescreening_data"), {}) or {}).get("engine") or {}).get("overrides")
	cleaned = clean_overrides(overrides)
	if (save or approve) and application.get("workflow_state") != PRESCREENING_STATE:
		raise frappe.ValidationError(f"Results can only be saved while the application is in {PRESCREENING_STATE}.")
	result = {"application": application_id, **evaluate(apply_overrides(application, cleaned))}
	if approve:
		_check_approval(result)
	if save or approve:
		status = APPROVED if approve else STAGE_STATUS[result["verdict"]]
		result.update(status=status, trigger=trigger, ran_on=str(now_datetime()), ran_by=frappe.session.user, overrides=cleaned)
		_store(application_id, result)
	return result


def _store(application_id: str, result: Dict[str, Any]):
	doc = frappe.get_doc(APPLICATION_DOCTYPE, application_id)
	data = load_json(doc.prescreening_data, {}) or {}
	data["engine"] = result
	doc.prescreening_data = dump_json(data)
	doc.prescreening_ruleset = (result.get("prescreening") or {}).get("ruleset")
	doc.eligibility_rule = (result.get("eligibility") or {}).get("rule")
	doc.eligible_amount = result.get("eligible_amount")
	doc.custom_status = result["status"]
	doc.save(ignore_permissions=True)


def on_enter_prescreening(application_id: str) -> Optional[Dict[str, Any]]:
	if frappe.db.get_value(APPLICATION_DOCTYPE, application_id, "workflow_state") != PRESCREENING_STATE:
		return None
	frappe.db.savepoint(SAVEPOINT)
	try:
		return evaluate_application(application_id, save=True, trigger=TRIGGER_WORKFLOW)
	except Exception as error:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.log_error(title="LOS engine failed", message=frappe.get_traceback())
		result = {
			"application": application_id,
			"verdict": VERDICT_REVIEW,
			"status": STAGE_STATUS[VERDICT_REVIEW],
			"error": str(error),
			"trigger": TRIGGER_WORKFLOW,
			"ran_on": str(now_datetime()),
			"ran_by": frappe.session.user,
		}
		_store(application_id, result)
		return result


def test_input(args: Dict[str, Any]):
	if args.get("application"):
		application = load_application(args["application"])
	else:
		application = load_json(args.get("data"), None)
		if not isinstance(application, dict):
			raise frappe.ValidationError("Send application (an application ID) or data (the application fields).")
	loan_product = args.get("loan_product") or application.get("loan_product")
	if not loan_product:
		raise frappe.ValidationError("loan_product is required.")
	if not frappe.db.exists(LOAN_PRODUCT_DOCTYPE, loan_product):
		raise frappe.ValidationError(f"Loan Product '{loan_product}' does not exist.")
	return application_facts(application), loan_product


def test_prescreening(args: Dict[str, Any]) -> Dict[str, Any]:
	facts, loan_product = test_input(args)
	return {"loan_product": loan_product, **prescreen(facts, loan_product)}


def test_eligibility(args: Dict[str, Any]) -> Dict[str, Any]:
	facts, loan_product = test_input(args)
	return {"loan_product": loan_product, **check_eligibility(facts, loan_product, _product(loan_product))}
