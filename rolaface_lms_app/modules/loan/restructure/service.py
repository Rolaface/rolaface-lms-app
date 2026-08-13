from rolaface_lms_app.modules.loan.category.utils import create_search_filters
import frappe
from typing import Dict, Any
from .constant import ALLOWED_RESTRUCTURE_FIELD, ALLOWED_CHARGE_FIELDS, RETURN_GET_FIELD_BY_ID, GET_FIELDS
from frappe.client import delete_doc

def create_restructure(data: Dict[str, Any]):
    restructure_doc = frappe.new_doc("Loan Restructure")
    for field in ALLOWED_RESTRUCTURE_FIELD:
        if field in data and data.get(field) is not None:
            restructure_doc.set(field, data.get(field))

    charges = data.get("loan_restructure_charges") or []
    if charges:
        for charge in charges:
            row = {
                key: charge.get(key)
                for key in ALLOWED_CHARGE_FIELDS
                if charge.get(key) is not None
            }
            restructure_doc.append("loan_restructure_charges", row)

    restructure_doc.insert(ignore_permissions=True)
    return restructure_doc.name

def update_restructure(data: Dict[str, Any]):
    name = data.get("name")

    restructure_doc = frappe.get_doc("Loan Restructure", name)

    for field in ALLOWED_RESTRUCTURE_FIELD:
        if field in data and data.get(field) is not None:
            restructure_doc.set(field, data.get(field))

    restructure_doc.set("loan_restructure_charges", [])
    if "loan_restructure_charges" in data:
        charges = data.get("loan_restructure_charges") or []
        for charge in charges:
            row = {
                key: charge.get(key)
                for key in ALLOWED_CHARGE_FIELDS
                if charge.get(key) is not None
            }
            restructure_doc.append("loan_restructure_charges", row)

    restructure_doc.save(ignore_permissions=True)
    return restructure_doc.name

def get_by_name(name):
    repayment_doc = frappe.get_doc("Loan Restructure", name)
    result = {field: repayment_doc.get(field) for field in RETURN_GET_FIELD_BY_ID}
    return result

def get_restructures(search, order_by, page, page_size):

    or_filters = None
    filters = {}
    response = {}

    if search:
           or_filters = create_search_filters(search)

    offset = (int(page) - 1) * int(page_size) 
    restructures = frappe.db.get_all( 'Loan Restructure', 
                                    filters=filters, or_filters=or_filters, fields=GET_FIELDS, 
                                    order_by=order_by, start=offset, page_length=int(page_size)
                                )
    total_restructures = len(frappe.db.get_all( 'Loan Restructure',
                                        filters=filters,
                                        or_filters=or_filters,
                                        pluck="name",
                                    ))

    total_pages = (total_restructures + int(page_size) - 1) // int(page_size)
    response= { 
                "restructures": restructures,
                "pagination":{
                                "page": page,
                                "page_size": page_size,
                                "total": total_restructures,
                                "total_pages": total_pages,
                                "has_next": int(page) < total_pages,
                                "has_prev": int(page) > 1,
                            }
                }
    return response

def delete_restructure(name):
    loan_repayment_schedule = frappe.db.get_value('Loan Repayment Schedule', {"loan_restructure": name}, 'name')
    if loan_repayment_schedule:
        delete_doc("Loan Repayment Schedule", loan_repayment_schedule)

    delete_doc("Loan Restructure", name)
    
