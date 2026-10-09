import frappe
from typing import Dict, Any
import json

from .constant import (
    PAYOUT_FREQUENCIES,
    REQUIRED_FIELDS,
    FIELD_LABELS,
    PERCENT_FIELDS,
    AMOUNT_FIELDS,
    TENURE_FIELDS,
    LIMIT_PAIRS,
    DEFAULT_WITHIN_LIMITS,
)


def _number(data: Dict[str, Any], field: str) -> float:
    try:
        return float(data.get(field))
    except (TypeError, ValueError):
        raise frappe.ValidationError(f"{FIELD_LABELS[field]} must be a number.")


def _validate_investment_product_payload(data: Dict[str, Any]):
    """
    Validates a complete product (on update: the saved values merged with the changes),
    so the cross-field rules (minimum <= maximum, defaults within limits) always see every value.
    """
    missing = [FIELD_LABELS[f] for f in REQUIRED_FIELDS if data.get(f) in (None, "")]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    for field in ("product_code", "product_name", "product_description"):
        if not str(data.get(field)).strip():
            raise frappe.ValidationError(f"{FIELD_LABELS[field]} cannot be empty.")

    for field in PERCENT_FIELDS:
        if data.get(field) in (None, ""):
            continue  # only Default Penalty Rate is optional
        value = _number(data, field)
        if value < 0 or value > 100:
            raise frappe.ValidationError(f"{FIELD_LABELS[field]} must be between 0 and 100.")

    for field in AMOUNT_FIELDS:
        if _number(data, field) <= 0:
            raise frappe.ValidationError(f"{FIELD_LABELS[field]} must be greater than 0.")

    for field in TENURE_FIELDS:
        value = _number(data, field)
        if value <= 0 or value != int(value):
            raise frappe.ValidationError(f"{FIELD_LABELS[field]} must be a whole number of months greater than 0.")

    for low, high in LIMIT_PAIRS:
        if _number(data, low) > _number(data, high):
            raise frappe.ValidationError(f"{FIELD_LABELS[low]} cannot be more than {FIELD_LABELS[high]}.")

    for field, (low, high) in DEFAULT_WITHIN_LIMITS.items():
        value = _number(data, field)
        if value < _number(data, low) or value > _number(data, high):
            raise frappe.ValidationError(
                f"{FIELD_LABELS[field]} must be between {FIELD_LABELS[low]} and {FIELD_LABELS[high]} "
                f"({data.get(low)} to {data.get(high)})."
            )

    if data.get("payout_frequency") not in PAYOUT_FREQUENCIES:
        raise frappe.ValidationError(
            f"Default Payout Frequency must be one of: {', '.join(PAYOUT_FREQUENCIES)}."
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