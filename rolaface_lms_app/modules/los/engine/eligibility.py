import re
from typing import Any, Dict, List, Optional

from frappe.utils import flt

from .prescreening import VERDICT_ELIGIBLE, VERDICT_NOT_ELIGIBLE, VERDICT_REVIEW

NET_SALARY = "net salary"
TOTAL_INCOME_BASIS = "total income"
BAND_DECLINE = "decline"
BAND_REVIEW = ("conditional", "manual review")

LIMIT_INCOME = "income"
LIMIT_AFFORDABILITY = "affordability"
LIMIT_CREDIT = "credit"
LIMIT_COLLATERAL = "collateral"
LIMIT_PRODUCT = "product"


def _number(value) -> Optional[float]:
	if value is None:
		return None
	if isinstance(value, (int, float)):
		return float(value)
	match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
	return float(match.group()) if match else None


def _match(sources: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
	key = name.strip().lower()
	if not key:
		return None
	for source in sources:
		source_name = str(source.get("name") or "").strip().lower()
		if source_name == key or source_name.startswith(key):
			return source
	return None


def _recognised(lines, sources, pct_key: str, unlisted_pct: float) -> float:
	total = 0.0
	for line in lines:
		source = _match(sources, line["source"])
		if source is None:
			pct = unlisted_pct
		elif not source.get("included"):
			pct = 0
		else:
			pct = flt(source.get(pct_key))
		total += line["monthly_amount"] * pct / 100
	return round(total, 2)


def _band(score, bands) -> Optional[Dict[str, Any]]:
	if score is None:
		return None
	for band in sorted(bands or [], key=lambda b: flt(b.get("min_score")), reverse=True):
		if band.get("min_score") not in (None, "") and flt(score) >= flt(band.get("min_score")):
			return band
	return None


def monthly_instalment(amount: float, annual_rate: float, months: int) -> float:
	if not amount or not months:
		return 0.0
	rate = flt(annual_rate) / 100 / 12
	if not rate:
		return amount / months
	return amount * rate / (1 - (1 + rate) ** -months)


def _condition_hit(operator: str, actual: float, low: Optional[float], high: Optional[float]) -> Optional[bool]:
	if low is None:
		return None
	return {
		"Equals": actual == low,
		"Less Than": actual < low,
		"Less Than or Equal": actual <= low,
		"Greater Than": actual > low,
		"Greater Than or Equal": actual >= low,
		"Between": high is not None and low <= actual <= high,
	}.get(operator)


def _check_rules(rules, values: Dict[str, Optional[float]], low_key: str, high_key: str):
	hits, not_checked = [], []
	for rule in rules or []:
		factor, operator = rule.get("factor"), rule.get("operator")
		actual = values.get(factor)
		hit = None if actual is None else _condition_hit(operator, actual, _number(rule.get(low_key)), _number(rule.get(high_key)))
		entry = {"factor": factor, "operator": operator, "value": rule.get(low_key), "value2": rule.get(high_key), "actual": actual}
		if hit is None:
			not_checked.append(entry)
		elif hit:
			hits.append(entry)
	return hits, not_checked


def run_eligibility(rule: Dict[str, Any], facts: Dict[str, Any], product: Dict[str, Any]) -> Dict[str, Any]:
	params = rule.get("formula_params") or {}
	tenure = int(flt(facts.get("tenure_months")))
	requested = flt(facts.get("requested_amount"))
	score = facts.get("credit_score")

	income = _recognised(facts.get("income_lines") or [], rule.get("income_sources") or [], "recognition_pct", flt(params.get("other_income_recognition")))
	obligations = _recognised(facts.get("obligation_lines") or [], rule.get("obligation_sources") or [], "pct", 100)
	net_salary = sum(line["monthly_amount"] for line in facts.get("income_lines") or [] if line["source"].strip().lower() == NET_SALARY)

	band = _band(score, rule.get("credit_bands"))
	band_multiple = flt(band.get("multiple")) if band else 0
	basis = str(band.get("basis") or "Net Salary") if band else "Net Salary"
	basis_income = income if basis.strip().lower() == TOTAL_INCOME_BASIS else net_salary

	max_emi = max(0.0, income * flt(params.get("max_emi_ratio")) / 100 - obligations)
	limits = [
		{"key": LIMIT_INCOME, "value": round(income * flt(params.get("salary_multiple")), 2), "recognised_income": income, "multiple": flt(params.get("salary_multiple"))},
		{
			"key": LIMIT_AFFORDABILITY,
			"value": round(max_emi * tenure * flt(params.get("affordability_buffer")) / 100, 2),
			"recognised_income": income,
			"max_emi_ratio": flt(params.get("max_emi_ratio")),
			"obligations": obligations,
			"max_emi": round(max_emi, 2),
			"tenure_months": tenure,
			"buffer": flt(params.get("affordability_buffer")),
		},
		{"key": LIMIT_CREDIT, "value": round(basis_income * band_multiple, 2), "basis": basis, "basis_income": basis_income, "multiple": band_multiple, "grade": band.get("grade") if band else None},
	]

	items = rule.get("collateral_items") or []
	if items:
		assets = []
		for asset in facts.get("collaterals") or []:
			item = next((i for i in items if str(i.get("type") or "").lower() == str(asset["collateral_type"]).lower()), None)
			lendable = asset["estimated_value"] * (1 - flt(item.get("haircut_pct")) / 100) * flt(item.get("max_ltv_pct")) / 100 if item else 0
			assets.append({"collateral_type": asset["collateral_type"], "estimated_value": asset["estimated_value"], "lendable": round(lendable, 2), "accepted": bool(item)})
		limits.append({"key": LIMIT_COLLATERAL, "value": round(sum(a["lendable"] for a in assets), 2), "assets": assets})

	product_max = flt(params.get("product_max")) or flt(product.get("maximum_loan_amount"))
	if product_max:
		limits.append({"key": LIMIT_PRODUCT, "value": product_max})

	limiting = min(limits, key=lambda limit: limit["value"])
	eligible = max(0.0, limiting["value"])

	dsr = round(obligations / income * 100, 2) if income else None
	new_emi = monthly_instalment(requested, flt(product.get("rate_of_interest")), tenure)
	emi_to_income = round((obligations + new_emi) / income * 100, 2) if income else None
	factor_values = {
		"Credit Score": flt(score) if score else None,
		"Debt Service Ratio (DSR)": dsr,
		"DSR Ratio": dsr,
		"EMI-to-Income Ratio": emi_to_income,
		"Loan Amount": requested or None,
	}
	hard_stops, hard_not_checked = _check_rules(rule.get("hard_stops"), factor_values, "value", "value2")
	reviews, review_not_checked = _check_rules(rule.get("manual_reviews"), factor_values, "value1", "value2")
	max_dti = flt(params.get("max_dti_ratio"))

	reasons, decision = [], VERDICT_ELIGIBLE
	no_income_entered = not facts.get("income_lines")
	if income <= 0 and not no_income_entered:
		reasons.append("No recognised income.")
	if band is None:
		reasons.append("Credit score is below every band." if score else "No credit score.")
	elif str(band.get("decision") or "").lower() == BAND_DECLINE:
		reasons.append(f"Credit band {band.get('grade')} declines.")
	reasons += [f"Hard stop: {h['factor']} {h['operator']} {h['value']}." for h in hard_stops]
	if dsr is not None and max_dti and dsr > max_dti:
		reasons.append(f"Debt service ratio {dsr:g}% is above {max_dti:g}%.")
	if not reasons and not no_income_entered and eligible <= 0:
		reasons.append(f"Eligible amount is 0 (limited by the {limiting['key']} limit).")

	if reasons:
		decision, eligible = VERDICT_NOT_ELIGIBLE, 0.0
	elif no_income_entered:
		decision, eligible = VERDICT_REVIEW, 0.0
		reasons.append("No income entered yet.")
	else:
		if str(band.get("decision") or "").lower() in BAND_REVIEW:
			reasons.append(f"Credit band {band.get('grade')} is {band.get('decision')}.")
		reasons += [f"{r['factor']} {r['operator']} {r['value']}{(' – ' + str(r['value2'])) if r['value2'] else ''}." for r in reviews]
		if reasons:
			decision = VERDICT_REVIEW

	return {
		"decision": decision,
		"eligible_amount": round(eligible, 2),
		"requested_amount": requested,
		"meets_request": eligible >= requested > 0,
		"limiting_factor": limiting["key"],
		"limits": limits,
		"grade": band.get("grade") if band else None,
		"band_decision": band.get("decision") if band else None,
		"recognised_income": income,
		"obligations": obligations,
		"net_salary": net_salary,
		"dsr": dsr,
		"max_dti_ratio": max_dti,
		"emi_to_income": emi_to_income,
		"max_emi_ratio": flt(params.get("max_emi_ratio")),
		"new_instalment": round(new_emi, 2),
		"rate_of_interest": flt(product.get("rate_of_interest")),
		"reasons": reasons,
		"hard_stops_hit": hard_stops,
		"manual_reviews_hit": reviews,
		"not_checked": hard_not_checked + review_not_checked,
	}
