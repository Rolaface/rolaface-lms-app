import frappe
from .utils import create_search_filters
from .constant import GET_FIELDS

def get_categories(disabled, search, order_by, page, page_size):

    or_filters = None
    filters = {}
    response = {}
    if disabled:
        filters["disabled"] = int(disabled)

    if search:
           or_filters = create_search_filters(search)

    offset = (int(page) - 1) * int(page_size) 
    categories = frappe.db.get_all( 'Loan Category', 
                                    filters=filters, or_filters=or_filters, fields=GET_FIELDS, 
                                    order_by=order_by, start=offset, page_length=int(page_size)
                                )
    total_categories = len(frappe.db.get_all( 'Loan Category',
                                        filters=filters,
                                        or_filters=or_filters,
                                        pluck="name",
                                    ))

    total_pages = (total_categories + int(page_size) - 1) // int(page_size)
    response= { 
                "categories": categories,
                "pagination":{
                                "page": page,
                                "page_size": page_size,
                                "total": total_categories,
                                "total_pages": total_pages,
                                "has_next": int(page) < total_pages,
                                "has_prev": int(page) > 1,
                            }
                }
    return response
    
def get_category_by_name(name):

    category = frappe.db.get_value('Loan Category', name, GET_FIELDS, as_dict=1)
    return category

def create_category(payload):
    doc = frappe.new_doc('Loan Category')
    doc.loan_category_code = payload.get("loan_category_code")
    doc.loan_category_name = payload.get("loan_category_name")
    doc.insert()
    return doc.loan_category_name

def update_category(payload):
    name = payload.get("name")
    if not name:
         raise frappe.DoesNotExistError("To update, please supply a loan category.")

    doc = doc = frappe.get_doc("Loan Category", name)
    doc.loan_category_name = payload.get("loan_category_name")
    doc.save()
    return doc.loan_category_name

def enable_disable_category(payload):
    name = payload.get("name")
    if not name:
         raise frappe.DoesNotExistError("To update, please supply a loan category.")

    doc = doc = frappe.get_doc("Loan Category", name)
    doc.disabled = payload.get("disabled")
    doc.save()
    return doc.loan_category_name