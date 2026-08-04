import frappe
from typing import Tuple, Dict, Any


def _validate_loan_security_payload(data: Dict[str, Any], is_update: bool = False):
    if not is_update:
        required_fields = ["loan_security_code", "loan_security_type", "loan_security_name"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    if data.get("loan_security_type") and not frappe.db.exists("Loan Security Type", data.get("loan_security_type")):
        raise frappe.DoesNotExistError(f"Loan Security Type '{data.get('loan_security_type')}' does not exist.")

    for percent_field, label in (("loan_to_value_ratio", "Loan To Value Ratio"), ("haircut", "Haircut %")):
        if percent_field in data and data.get(percent_field) is not None:
            try:
                value = float(data.get(percent_field))
            except (TypeError, ValueError):
                raise frappe.ValidationError(f"{label} must be a number.")
            if value < 0 or value > 100:
                raise frappe.ValidationError(f"{label} must be between 0 and 100.")

    if "original_security_value" in data and data.get("original_security_value") is not None:
        try:
            value = float(data.get("original_security_value"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Original Security Value must be a number.")
        if value < 0:
            raise frappe.ValidationError("Original Security Value cannot be negative.")


def _build_loan_security_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("disabled") is not None:
        filters["disabled"] = args.get("disabled")

    if args.get("loan_security_type"):
        filters["loan_security_type"] = args.get("loan_security_type")

    return filters