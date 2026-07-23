import frappe
from typing import Dict, Any
import json
from frappe.utils import flt, cint

def validate_loan_product_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        if not data.get("product_code"):
            raise frappe.ValidationError("product_code is required.")
        if not data.get("product_name"):
            raise frappe.ValidationError("product_name is required.")

    if "rate_of_interest" in data:
        if flt(data.get("rate_of_interest")) < 0:
            raise frappe.ValidationError("rate_of_interest cannot be negative.")
            
    if "maximum_loan_amount" in data:
        if flt(data.get("maximum_loan_amount")) < 0:
            raise frappe.ValidationError("maximum_loan_amount cannot be negative.")
            
    if "penalty_interest_rate" in data:
        if flt(data.get("penalty_interest_rate")) < 0:
            raise frappe.ValidationError("penalty_interest_rate cannot be negative.")

    company = data.get("company")
    if company and not frappe.db.exists("Company", company):
        raise frappe.ValidationError(f"Company '{company}' does not exist.")

    account_fields = [
        "disbursement_account", "payment_account", "loan_account", 
        "interest_income_account", "penalty_income_account"
    ]
    for acc_field in account_fields:
        acc = data.get(acc_field)
        if acc and not frappe.db.exists("Account", acc):
            raise frappe.ValidationError(f"Account '{acc}' provided for {acc_field} does not exist.")

    charges = data.get("loan_charges")
    if charges is not None:
        if not isinstance(charges, list):
            raise frappe.ValidationError("'loan_charges' must be an array.")
            
        for idx, charge in enumerate(charges):
            if not charge.get("charge_type"):
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: 'charge_type' is required.")
            
            pct = flt(charge.get("percentage"))
            amt = flt(charge.get("amount"))
            
            if pct < 0 or amt < 0:
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: Percentage and Amount cannot be negative.")
            
            if pct == 0 and amt == 0:
                 raise frappe.ValidationError(f"Row {idx+1} in loan_charges: Either Percentage or Amount must be greater than 0.")
    if data.get("product_code") or data.get("product_name"):
        or_filters = []
        if data.get("product_code"):
            or_filters.append(["product_code", "=", data["product_code"]])
        if data.get("product_name"):
            or_filters.append(["product_name", "=", data["product_name"]])
            
        filters = [["docstatus", "<", 2]]
        
        existing = frappe.get_all(
            "Loan Product",
            filters=filters,
            or_filters=or_filters,
            fields=["name", "product_code", "product_name"]
        )
        
        for ext in existing:
            if is_update and ext.name == data.get("name"):
                continue
            if ext.product_code == data.get("product_code"):
                raise frappe.DuplicateEntryError(f"Loan Product with Product Code '{data['product_code']}' already exists.")
            if ext.product_name == data.get("product_name"):
                raise frappe.DuplicateEntryError(f"Loan Product with Product Name '{data['product_name']}' already exists.")


def build_loan_product_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]

    if args.get("disabled") is not None:
        frappe_filters["disabled"] = cint(args["disabled"])

    if args.get("loan_category"):
        frappe_filters["loan_category"] = ["in", args["loan_category"]] if isinstance(args["loan_category"], list) else args["loan_category"]

    if args.get("is_term_loan") is not None:
        frappe_filters["is_term_loan"] = cint(args["is_term_loan"])

    minRate = args.get("minRate")
    maxRate = args.get("maxRate")
    if minRate and maxRate:
        frappe_filters["rate_of_interest"] = ["between", [flt(minRate), flt(maxRate)]]
    elif minRate:
        frappe_filters["rate_of_interest"] = [">=", flt(minRate)]
    elif maxRate:
        frappe_filters["rate_of_interest"] = ["<=", flt(maxRate)]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["maximum_loan_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["maximum_loan_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["maximum_loan_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters


def handle_api_error(e: Exception, context_message: str):
    frappe.db.rollback()
    
    if not isinstance(e, (frappe.ValidationError, frappe.DuplicateEntryError, frappe.DoesNotExistError)):
        frappe.log_error(frappe.get_traceback(), context_message)

    error_message = str(e).strip()
    import re
    error_message = re.sub('<[^<]+?>', '', error_message)

    status_code = 500
    status_type = "error"

    if isinstance(e, frappe.DoesNotExistError):
        status_code = 404
        status_type = "fail"
    elif isinstance(e, frappe.DuplicateEntryError):
        status_code = 409
        status_type = "fail"
    elif isinstance(e, frappe.PermissionError):
        status_code = 403
        status_type = "fail"
        error_message = "You do not have permission to perform this action."
    elif isinstance(e, frappe.ValidationError):
        status_code = 400
        status_type = "fail"

    from rolaface_lms_app.utils.api_response import send_response 
    
    return send_response(
        status=status_type,
        message=error_message,
        status_code=status_code,
        http_status=status_code,
    )

def sync_loan_charges(product_doc, charges_payload: list) -> bool:
    if charges_payload is None:
        return False
        
    product_doc.set("loan_charges", [])
    
    for charge in charges_payload:
        product_doc.append("loan_charges", {
            "charge_type": charge.get("charge_type"),
            "charge_based_on": charge.get("charge_based_on"),
            "percentage": flt(charge.get("percentage")),
            "amount": flt(charge.get("amount"))
        })
    return True