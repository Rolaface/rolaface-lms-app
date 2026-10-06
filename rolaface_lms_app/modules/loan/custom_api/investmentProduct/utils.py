import frappe
from typing import Dict, Any
import json

from .constant import PAYOUT_FREQUENCIES


def _validate_investment_product_payload(data: Dict[str, Any], is_update: bool = False):
    if not is_update:
        required_fields = [
            "product_name", "tenure", "minimum_investment",
            "interest_rate", "payout_frequency",
        ]
        missing = [f for f in required_fields if data.get(f) in (None, "")]
        if missing:
            raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    if "product_name" in data and data.get("product_name") is not None:
        if not str(data.get("product_name")).strip():
            raise frappe.ValidationError("Product Name cannot be empty.")

    if "tenure" in data and data.get("tenure") is not None:
        try:
            value = float(data.get("tenure"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Tenure (months) must be a number.")
        if value <= 0 or value != int(value):
            raise frappe.ValidationError("Tenure (months) must be a whole number greater than 0.")

    if "minimum_investment" in data and data.get("minimum_investment") is not None:
        try:
            value = float(data.get("minimum_investment"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Minimum Investment must be a number.")
        if value < 0:
            raise frappe.ValidationError("Minimum Investment cannot be negative.")

    if "interest_rate" in data and data.get("interest_rate") is not None:
        try:
            value = float(data.get("interest_rate"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Interest Rate must be a number.")
        if value < 0 or value > 100:
            raise frappe.ValidationError("Interest Rate must be between 0 and 100.")

    if "payout_frequency" in data and data.get("payout_frequency") is not None:
        if data.get("payout_frequency") not in PAYOUT_FREQUENCIES:
            raise frappe.ValidationError(
                f"Payout Frequency must be one of: {', '.join(PAYOUT_FREQUENCIES)}."
            )


def _build_investment_product_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("disabled") is not None:
        filters["disabled"] = int(args.get("disabled"))

    if args.get("payout_frequency"):
        payout_frequency = args.get("payout_frequency")
        if isinstance(payout_frequency, str):
            try:
                payout_frequency = json.loads(payout_frequency)
            except json.JSONDecodeError:
                payout_frequency = [payout_frequency]
        if not isinstance(payout_frequency, list):
            payout_frequency = [payout_frequency]

        filters["payout_frequency"] = ["in", payout_frequency]

    return filters