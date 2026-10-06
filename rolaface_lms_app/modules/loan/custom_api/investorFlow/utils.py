import frappe
from frappe.utils import getdate
from typing import Dict, Any
import json

from .constant import REPAYMENT_FREQUENCIES


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