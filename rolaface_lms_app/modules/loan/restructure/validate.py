import frappe
from .constant import RESTRUCTURABLE_LOAN_STATUSES

def validate_loan_status(loan):
    status = frappe.db.get_value("Loan", loan, "status")
    if status is None:
        frappe.throw(f"Loan '{loan}' does not exist.")
    if status not in RESTRUCTURABLE_LOAN_STATUSES:
        frappe.throw(
            f"Restructuring is allowed only for Disbursed or Partially Disbursed loans. "
            f"Loan '{loan}' is currently '{status}'."
        )

def validate_create_payload(data):
    if not data.get("loan"):
        frappe.throw("loan is required")
    if not data.get("applicant"):
        frappe.throw("applicant is required")
    validate_loan_status(data.get("loan"))

def validate_update_payload(data):
    name = data.get("name")
    if not name:
        frappe.throw("name is required")

    if not frappe.db.exists("Loan Restructure", name):
        frappe.throw(f"Loan Restructure '{name}' does not exist.")

    if not data.get("loan"):
            frappe.throw("loan is required")
    if not data.get("applicant"):
            frappe.throw("applicant is required")
    validate_loan_status(data.get("loan"))

def validate_get_by_id(name):
    if not name.get("name"):
        frappe.throw("name is required")
    if not frappe.db.exists("Loan Restructure", name.get("name")):
        frappe.throw(f"Loan Restructure '{name}' does not exist.")