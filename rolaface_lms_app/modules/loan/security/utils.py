import frappe
from frappe.utils import flt, cint
from typing import Dict, Any

def validate_loan_security_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = ["loan_security_code", "loan_security_name", "loan_security_type"]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    numeric_fields = [
        "haircut", "original_security_value", "utilized_security_value", 
        "available_security_value", "loan_to_value_ratio"
    ]
    for field in numeric_fields:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"'{field}' cannot be negative.")

    if data.get("loan_security_type") and not frappe.db.exists("Loan Security Type", data.get("loan_security_type")):
        raise frappe.ValidationError(f"Loan Security Type '{data.get('loan_security_type')}' does not exist.")

def build_loan_security_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("loan_security_type"):
        frappe_filters["loan_security_type"] = args["loan_security_type"]
        
    if "disabled" in args:
        frappe_filters["disabled"] = cint(args["disabled"])

    min_val = args.get("minOriginalValue")
    max_val = args.get("maxOriginalValue")
    if min_val and max_val:
        frappe_filters["original_security_value"] = ["between", [flt(min_val), flt(max_val)]]
    elif min_val:
        frappe_filters["original_security_value"] = [">=", flt(min_val)]
    elif max_val:
        frappe_filters["original_security_value"] = ["<=", flt(max_val)]
        
    min_avail = args.get("minAvailableValue")
    max_avail = args.get("maxAvailableValue")
    if min_avail and max_avail:
        frappe_filters["available_security_value"] = ["between", [flt(min_avail), flt(max_avail)]]
    elif min_avail:
        frappe_filters["available_security_value"] = [">=", flt(min_avail)]
    elif max_avail:
        frappe_filters["available_security_value"] = ["<=", flt(max_avail)]

    return frappe_filters