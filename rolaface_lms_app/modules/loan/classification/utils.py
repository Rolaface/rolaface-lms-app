import frappe
from frappe.utils import flt
from typing import Dict, Any

def get_target_company(data: Dict[str, Any] = None) -> str:
    """Gets the company from payload, or falls back to user default."""
    company = data.get("company") if data else None
    if not company:
        company = frappe.defaults.get_user_default("Company")
    if not company:
        raise frappe.ValidationError("Company is required. Provide it in the payload or set a Default Company in Frappe.")
    if not frappe.db.exists("Company", company):
        raise frappe.ValidationError(f"Company '{company}' does not exist.")
    return company

def validate_classification_payload(data: Dict[str, Any], is_update=False):
    """Validates structure and numeric boundaries."""
    if not is_update:
        if not data.get("classificationCode"):
            raise frappe.ValidationError("classificationCode is required.")
        if not data.get("classificationName"):
            raise frappe.ValidationError("classificationName is required.")

    for field in ["minDpdRange", "maxDpdRange", "provisionRate"]:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"{field} cannot be negative.")

def validate_dpd_logic(min_dpd: float, max_dpd: float):
    """Ensures DPD range logic is valid."""
    if flt(min_dpd) > flt(max_dpd):
        raise frappe.ValidationError(f"Invalid Range: Minimum DPD ({min_dpd}) cannot exceed Maximum DPD ({max_dpd}).")