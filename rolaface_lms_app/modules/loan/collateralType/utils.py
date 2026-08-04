import frappe
from typing import Tuple, Dict, Any


def _validate_loan_security_type_payload(data: Dict[str, Any], is_update: bool = False):
    if not is_update and not data.get("loan_security_type"):
        raise frappe.ValidationError("Loan Security Type is required.")

    for percent_field, label in (("loan_to_value_ratio", "Loan To Value Ratio"), ("haircut", "Haircut %")):
        if percent_field in data and data.get(percent_field) is not None:
            try:
                value = float(data.get(percent_field))
            except (TypeError, ValueError):
                raise frappe.ValidationError(f"{label} must be a number.")
            if value < 0 or value > 100:
                raise frappe.ValidationError(f"{label} must be between 0 and 100.")


def _build_loan_security_type_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("disabled") is not None:
        filters["disabled"] = args.get("disabled")

    if args.get("loan_security_type"):
        filters["loan_security_type"] = ["like", f"%{str(args.get('loan_security_type')).strip()}%"]

    return filters
