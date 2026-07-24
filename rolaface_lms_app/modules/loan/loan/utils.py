import frappe
from frappe.utils import flt
from typing import Dict, Any

def validate_loan_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = ["applicant_type", "applicant", "loan_product", "company", "loan_amount"]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    numeric_fields = ["loan_amount", "rate_of_interest", "repayment_periods"]
    for field in numeric_fields:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"'{field}' cannot be negative.")

    if data.get("company") and not frappe.db.exists("Company", data.get("company")):
        raise frappe.ValidationError(f"Company '{data.get('company')}' does not exist.")
        
    if data.get("loan_product") and not frappe.db.exists("Loan Product", data.get("loan_product")):
        raise frappe.ValidationError(f"Loan Product '{data.get('loan_product')}' does not exist.")

    charges = data.get("loan_charges")
    if charges is not None:
        if not isinstance(charges, list):
            raise frappe.ValidationError("'loan_charges' must be an array.")
            
        valid_treatments = ["Billed Separately", "Add to first repayment"]
            
        for idx, charge in enumerate(charges):
            if not charge.get("charge"):
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: 'charge' is required.")
            
            amt = flt(charge.get("amount"))
            if amt < 0:
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: Amount cannot be negative.")
                
            if charge.get("account") and not frappe.db.exists("Account", charge.get("account")):
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: Account '{charge.get('account')}' does not exist.")
                
            treatment = charge.get("treatment_of_charge")
            if treatment and treatment not in valid_treatments:
                raise frappe.ValidationError(f"Row {idx+1} in loan_charges: 'treatment_of_charge' must be one of {valid_treatments}.")

    account_fields = [
        "disbursement_account", "payment_account", "loan_account", 
        "interest_income_account", "penalty_income_account"
    ]
    for acc_field in account_fields:
        acc = data.get(acc_field)
        if acc and not frappe.db.exists("Account", acc):
            raise frappe.ValidationError(f"Account '{acc}' provided for {acc_field} does not exist.")

def build_loan_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]
        
    if args.get("status"):
        frappe_filters["status"] = ["in", args["status"]] if isinstance(args["status"], list) else args["status"]

    if args.get("applicant"):
        frappe_filters["applicant"] = args["applicant"]
        
    if args.get("loan_product"):
        frappe_filters["loan_product"] = args["loan_product"]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["loan_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["loan_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["loan_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters

def sync_loan_charges(loan_doc, charges_payload: list) -> bool:
    if charges_payload is None:
        return False
        
    loan_doc.set("loan_charges", [])
    
    for charge in charges_payload:
        loan_doc.append("loan_charges", {
            "charge": charge.get("charge"),
            "amount": flt(charge.get("amount")),
            "account": charge.get("account"),
            "treatment_of_charge": charge.get("treatment_of_charge")
        })
    return True