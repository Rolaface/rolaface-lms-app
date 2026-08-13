import frappe

def validate_create_payload(data):
    if not data.get("loan"):
        frappe.throw("loan is required")
    if not data.get("applicant"):
        frappe.throw("applicant is required")

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

def validate_get_by_id(name):
    if not name.get("name"):
        frappe.throw("name is required")
    print(repr(name))  # repr() will reveal hidden whitespace/type issues immediately
    print(frappe.db.exists("Loan Restructure", name))
    if not frappe.db.exists("Loan Restructure", name.get("name")):
        frappe.throw(f"Loan Restructure '{name}' does not exist.")