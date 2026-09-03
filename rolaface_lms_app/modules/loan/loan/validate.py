import frappe

def validate_create_payload(payload):
    if payload.get("repayment_start_date") and payload.get("repayment_start_date") < payload.get("posting_date"):
        frappe.throw("Repayment date cannot be before the Value date.")

def validate_update_payload(payload):
    if payload.get("repayment_start_date") and payload.get("repayment_start_date") < payload.get("posting_date"):
        frappe.throw("Repayment date cannot be before the Value date.")
