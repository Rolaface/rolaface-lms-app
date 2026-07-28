import frappe
from frappe.utils import flt
from typing import Dict, Any

def validate_loan_write_off_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = ["loan", "write_off_amount", "write_off_account", "company"]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    if "write_off_amount" in data and flt(data.get("write_off_amount")) < 0:
        raise frappe.ValidationError("'write_off_amount' cannot be negative.")

    # Validate Foreign Keys
    if data.get("company") and not frappe.db.exists("Company", data.get("company")):
        raise frappe.ValidationError(f"Company '{data.get('company')}' does not exist.")
        
    if data.get("loan") and not frappe.db.exists("Loan", data.get("loan")):
        raise frappe.ValidationError(f"Loan '{data.get('loan')}' does not exist.")

    if data.get("write_off_account") and not frappe.db.exists("Account", data.get("write_off_account")):
        raise frappe.ValidationError(f"Account '{data.get('write_off_account')}' does not exist.")
        
    if data.get("cost_center") and not frappe.db.exists("Cost Center", data.get("cost_center")):
        raise frappe.ValidationError(f"Cost Center '{data.get('cost_center')}' does not exist.")


def build_loan_write_off_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]
        
    if args.get("loan"):
        frappe_filters["loan"] = args["loan"]
        
    if args.get("applicant"):
        frappe_filters["applicant"] = args["applicant"]
        
    if "docstatus" in args:
        frappe_filters["docstatus"] = args["docstatus"]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["write_off_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["write_off_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["write_off_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters