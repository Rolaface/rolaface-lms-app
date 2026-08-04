import frappe
from frappe.utils import flt, cint
from typing import Dict, Any

def validate_loan_security_type_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        if not data.get("loan_security_type"):
            raise frappe.ValidationError("'loan_security_type' is required.")

    numeric_fields = ["haircut", "loan_to_value_ratio"]
    for field in numeric_fields:
        if field in data:
            val = flt(data.get(field))
            if val < 0:
                raise frappe.ValidationError(f"'{field}' cannot be negative.")
            if val > 100:
                frappe.throw(f"'{field}' cannot exceed 100.")

def build_loan_security_type_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if "disabled" in args:
        frappe_filters["disabled"] = cint(args["disabled"])

    min_haircut = args.get("minHaircut")
    max_haircut = args.get("maxHaircut")
    if min_haircut and max_haircut:
        frappe_filters["haircut"] = ["between", [flt(min_haircut), flt(max_haircut)]]
    elif min_haircut:
        frappe_filters["haircut"] = [">=", flt(min_haircut)]
    elif max_haircut:
        frappe_filters["haircut"] = ["<=", flt(max_haircut)]

    return frappe_filters