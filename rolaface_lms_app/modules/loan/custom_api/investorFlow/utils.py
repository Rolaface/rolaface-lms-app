import frappe
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate, cint, flt, nowdate
from typing import Dict, Any, List
import json

from .constant import (
    REPAYMENT_FREQUENCIES,
    SCHEDULE_TABLE_FIELD,
    INTEREST_FREQUENCY_FIELD,
    INTEREST_FREQUENCY_MONTHLY,
    INTEREST_FREQUENCY_YEARLY,
    INTEREST_FREQUENCIES,
)

# Used to count leftover days as a fraction of a month.
AVERAGE_DAYS_PER_MONTH = 30.4375


def schedule_version(row) -> int:
    """Version of a schedule row; rows saved before the version field existed count as version 1."""
    return cint(row.get("version")) or 1


def current_schedule(investor_flow_doc) -> List:
    """The repayment schedule in use: the rows of the highest version, in order."""
    rows = investor_flow_doc.get(SCHEDULE_TABLE_FIELD) or []
    if not rows:
        return []
    latest = max(schedule_version(r) for r in rows)
    return sorted((r for r in rows if schedule_version(r) == latest), key=lambda r: r.idx)


def schedule_history(investor_flow_doc) -> List[Dict[str, Any]]:
    """Earlier versions of the schedule (newest first): [{"version": n, "rows": [...]}]."""
    rows = investor_flow_doc.get(SCHEDULE_TABLE_FIELD) or []
    if not rows:
        return []
    latest = max(schedule_version(r) for r in rows)
    versions: Dict[int, list] = {}
    for r in rows:
        v = schedule_version(r)
        if v < latest:
            versions.setdefault(v, []).append(r)
    return [
        {"version": v, "rows": sorted(versions[v], key=lambda r: r.idx)}
        for v in sorted(versions, reverse=True)
    ]


def _parse_date(value, label: str):
    try:
        return getdate(value)
    except Exception:
        raise frappe.ValidationError(f"{label} must be a valid date (YYYY-MM-DD).")


def _validate_investor_flow_payload(
    data: Dict[str, Any], is_update: bool = False, existing_doc=None
):
    """
    existing_doc is passed on update so the date rule can be checked even when
    only one of the two dates is sent.
    """
    if not is_update:
        required_fields = [
            "investor", "investment_product", "investment_amount", "repayment_frequency",
            "maturity_date", "interest_rate", "first_repayment_date",
        ]
        missing = [f for f in required_fields if data.get(f) in (None, "")]
        if missing:
            raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    if data.get("investor") and not frappe.db.exists("Customer", data.get("investor")):
        raise frappe.DoesNotExistError(f"Investor (Customer) '{data.get('investor')}' does not exist.")

    if data.get("investment_product") and not frappe.db.exists(
        "Custom Investment Product", data.get("investment_product")
    ):
        raise frappe.DoesNotExistError(
            f"Investment Product '{data.get('investment_product')}' does not exist."
        )

    if "investment_amount" in data and data.get("investment_amount") is not None:
        try:
            value = float(data.get("investment_amount"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Investment Amount must be a number.")
        if value <= 0 or value != int(value):
            raise frappe.ValidationError("Investment Amount must be a whole number greater than 0.")

    for percent_field, label in (("interest_rate", "Interest Rate"), ("penalty_rate", "Penalty Rate")):
        if percent_field in data and data.get(percent_field) is not None:
            try:
                value = float(data.get(percent_field))
            except (TypeError, ValueError):
                raise frappe.ValidationError(f"{label} must be a number.")
            if value < 0 or value > 100:
                raise frappe.ValidationError(f"{label} must be between 0 and 100.")

    if "repayment_frequency" in data and data.get("repayment_frequency") is not None:
        if data.get("repayment_frequency") not in REPAYMENT_FREQUENCIES:
            raise frappe.ValidationError(
                f"Repayment Frequency must be one of: {', '.join(REPAYMENT_FREQUENCIES)}."
            )

    first_repayment_date = None
    maturity_date = None

    if data.get("first_repayment_date"):
        first_repayment_date = _parse_date(data.get("first_repayment_date"), "First Repayment Date")
    elif existing_doc and existing_doc.get("first_repayment_date"):
        first_repayment_date = getdate(existing_doc.get("first_repayment_date"))

    if data.get("maturity_date"):
        maturity_date = _parse_date(data.get("maturity_date"), "Maturity Date")
    elif existing_doc and existing_doc.get("maturity_date"):
        maturity_date = getdate(existing_doc.get("maturity_date"))

    if first_repayment_date and maturity_date and maturity_date <= first_repayment_date:
        raise frappe.ValidationError("Maturity Date must be after the First Repayment Date.")

    if data.get(INTEREST_FREQUENCY_FIELD) not in (None, "") and data.get(INTEREST_FREQUENCY_FIELD) not in INTEREST_FREQUENCIES:
        raise frappe.ValidationError(f"Interest Frequency must be one of: {', '.join(INTEREST_FREQUENCIES)}.")
    # Product ranges (amount, rate, tenure) are warnings only; they never block (see product_limit_warnings).


def _tenure_months(start, end) -> float:
    """Months from start to end; leftover days count as a fraction of a month."""
    diff = relativedelta(end, start)
    return diff.years * 12 + diff.months + diff.days / AVERAGE_DAYS_PER_MONTH


def interest_frequency_of(doc=None, data: Dict[str, Any] = None) -> str:
    """The investment's interest basis: sent value, else the saved one, else its product's, else Yearly."""
    data = data or {}
    value = data.get(INTEREST_FREQUENCY_FIELD) or (doc.get(INTEREST_FREQUENCY_FIELD) if doc else None)
    if not value:
        product = data.get("investment_product") or (doc.get("investment_product") if doc else None)
        if product:
            value = frappe.db.get_value("Custom Investment Product", product, INTEREST_FREQUENCY_FIELD)
    return value if value in INTEREST_FREQUENCIES else INTEREST_FREQUENCY_YEARLY


def monthly_interest_fraction(rate, interest_frequency: str) -> float:
    """Interest for one month as a fraction of principal (12% Yearly = 1% Monthly = 0.01)."""
    return flt(rate) / 100 if interest_frequency == INTEREST_FREQUENCY_MONTHLY else flt(rate) / 1200


def product_limit_warnings(data: Dict[str, Any], existing_doc=None, maturity_date=None) -> List[str]:
    """
    Where the investment is outside its product's ranges (amount, interest rate, tenure).
    These are warnings only: the investment can still be saved.
    """
    def value(field):
        if data.get(field) not in (None, ""):
            return data.get(field)
        return existing_doc.get(field) if existing_doc else None

    product = value("investment_product")
    if not product:
        return []
    limits = frappe.db.get_value(
        "Custom Investment Product", product,
        ["product_name", "minimum_investment", "maximum_investment", "min_interest_rate",
         "maximum_interest_rate", "minimum_tenure", "maximum_tenure", INTEREST_FREQUENCY_FIELD],
        as_dict=True,
    )
    if not limits:
        return []
    name = limits.product_name
    warnings = []

    amount = value("investment_amount")
    if amount not in (None, ""):
        if flt(limits.minimum_investment) and flt(amount) < flt(limits.minimum_investment):
            warnings.append(f"Investment amount is below the Minimum Investment of {name} ({flt(limits.minimum_investment):,.2f}).")
        if flt(limits.maximum_investment) and flt(amount) > flt(limits.maximum_investment):
            warnings.append(f"Investment amount is above the Maximum Investment of {name} ({flt(limits.maximum_investment):,.2f}).")

    rate = value("interest_rate")
    if rate not in (None, "") and flt(limits.maximum_interest_rate):
        # Compared on the same basis (a monthly rate is x12 per annum).
        product_basis = limits.get(INTEREST_FREQUENCY_FIELD) or INTEREST_FREQUENCY_YEARLY
        investment_basis = interest_frequency_of(existing_doc, data)
        to_yearly = lambda r, basis: flt(r) * 12 if basis == INTEREST_FREQUENCY_MONTHLY else flt(r)
        rate_y = to_yearly(rate, investment_basis)
        low_y = to_yearly(limits.min_interest_rate, product_basis)
        high_y = to_yearly(limits.maximum_interest_rate, product_basis)
        if rate_y < low_y or rate_y > high_y:
            unit = "per month" if product_basis == INTEREST_FREQUENCY_MONTHLY else "per annum"
            warnings.append(
                f"Interest rate is outside the range of {name} "
                f"({flt(limits.min_interest_rate):g}% to {flt(limits.maximum_interest_rate):g}% {unit})."
            )

    if maturity_date and cint(limits.maximum_tenure):
        # Tenure runs from the day the investment is created (today for a new one).
        start = getdate(existing_doc.creation) if existing_doc else getdate(nowdate())
        months = _tenure_months(start, maturity_date)
        low, high = cint(limits.minimum_tenure), cint(limits.maximum_tenure)
        if months < low or months > high:
            warnings.append(
                f"Tenure ({months:.1f} months) is outside the range of {name} ({low} to {high} months)."
            )
    return warnings


def _as_list(value):
    """Accepts a single value, a list, or a JSON-encoded list."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        value = [value]
    return value


def _build_investor_flow_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("investor"):
        filters["investor"] = ["in", _as_list(args.get("investor"))]

    if args.get("investment_product"):
        filters["investment_product"] = ["in", _as_list(args.get("investment_product"))]

    if args.get("repayment_frequency"):
        filters["repayment_frequency"] = ["in", _as_list(args.get("repayment_frequency"))]

    if args.get("status"):
        filters["status"] = ["in", _as_list(args.get("status"))]

    return filters