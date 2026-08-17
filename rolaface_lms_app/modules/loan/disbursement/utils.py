import frappe
from frappe.utils import flt
from typing import Dict, Any
import json

def validate_loan_disbursement_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = ["against_loan", "disbursed_amount", "company"]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    numeric_fields = ["disbursed_amount", "sanctioned_loan_amount", "current_disbursed_amount", "monthly_repayment_amount"]
    for field in numeric_fields:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"'{field}' cannot be negative.")

    if data.get("company") and not frappe.db.exists("Company", data.get("company")):
        raise frappe.ValidationError(f"Company '{data.get('company')}' does not exist.")
        
    if data.get("against_loan") and not frappe.db.exists("Loan", data.get("against_loan")):
        raise frappe.ValidationError(f"Loan '{data.get('against_loan')}' does not exist.")

    account_fields = [
        "disbursement_account", "refund_account", "loan_account", "bank_account"
    ]
    for acc_field in account_fields:
        acc = data.get(acc_field)
        if acc and not frappe.db.exists("Account", acc):
            raise frappe.ValidationError(f"Account '{acc}' provided for {acc_field} does not exist.")

    charges = data.get("disbursement_charges")
    if charges is not None:
        if not isinstance(charges, list):
            raise frappe.ValidationError("'disbursement_charges' must be an array.")
            
        valid_treatments = ["Billed Separately", "Add to first repayment"]
            
        for idx, charge in enumerate(charges):
            if not charge.get("charge"):
                raise frappe.ValidationError(f"Row {idx+1} in disbursement_charges: 'charge' is required.")
            
            amt = flt(charge.get("amount"))
            if amt < 0:
                raise frappe.ValidationError(f"Row {idx+1} in disbursement_charges: Amount cannot be negative.")
                
            if charge.get("account") and not frappe.db.exists("Account", charge.get("account")):
                raise frappe.ValidationError(f"Row {idx+1} in disbursement_charges: Account '{charge.get('account')}' does not exist.")
                
            treatment = charge.get("treatment_of_charge")
            if treatment and treatment not in valid_treatments:
                raise frappe.ValidationError(f"Row {idx+1} in disbursement_charges: 'treatment_of_charge' must be one of {valid_treatments}.")


def sync_loan_disbursement_charges(loan_disbursement_doc, charges_payload: list) -> bool:
    if charges_payload is None:
        return False
        
    if loan_disbursement_doc.get("loan_disbursement_charges"):
        loan_disbursement_doc.get("loan_disbursement_charges").clear()
    else:
        loan_disbursement_doc.loan_disbursement_charges = []
    
    for charge in charges_payload:
        loan_disbursement_doc.append("loan_disbursement_charges", {
            "charge": charge.get("charge"),
            "amount": flt(charge.get("amount")),
            "account": charge.get("account"),
            "treatment_of_charge": charge.get("treatment_of_charge")
        })
    return True

def build_loan_disbursement_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]
        
    if args.get("status"):
        status = args.get("status")
        if isinstance(status, str):
            try:
                status = json.loads(status)
            except json.JSONDecodeError:
                status = [status]
        
        frappe_filters["status"] = ["in",status]

    if args.get("against_loan"):
        frappe_filters["against_loan"] = args["against_loan"]
        
    if args.get("applicant"):
        frappe_filters["applicant"] = args["applicant"]

    if args.get("applicant_type"):
        applicant_type = args.get("applicant_type")
        if isinstance(applicant_type, str):
            try:
                applicant_type = json.loads(applicant_type)
            except json.JSONDecodeError:
                applicant_type = [applicant_type]
                
        frappe_filters["applicant_type"] = ["in",applicant_type]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["disbursed_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["disbursed_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["disbursed_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters