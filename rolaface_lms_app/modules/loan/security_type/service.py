import frappe
from typing import Tuple, Dict, Any
from .utils import build_loan_security_type_filters, validate_loan_security_type_payload
from .constant import (
    ALLOWED_LOAN_SECURITY_TYPE_FIELDS, 
    RETURN_FIELDS_GET_ALL, 
    RETURN_FIELDS_GET_BY_ID, 
    ALLOWED_SORT_FIELDS
)

def create_loan_security_type(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_loan_security_type_payload(data, is_update=False)

    doc = frappe.new_doc("Loan Security Type")
    
    for field in ALLOWED_LOAN_SECURITY_TYPE_FIELDS:
        if field in data and data.get(field) is not None:
            doc.set(field, data.get(field))
            
    doc.insert(ignore_permissions=True)
    return get_loan_security_type_by_id(doc.name)


def update_loan_security_type(type_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Security Type", type_id):
        raise frappe.DoesNotExistError(f"Loan Security Type '{type_id}' does not exist.")

    doc = frappe.get_doc("Loan Security Type", type_id)
    
    if doc.docstatus == 1:
        raise frappe.ValidationError(f"Cannot update submitted Loan Security Type '{type_id}'.")

    validate_loan_security_type_payload(data, is_update=True)
    has_changes = False

    for field in ALLOWED_LOAN_SECURITY_TYPE_FIELDS:
        if field in data and data.get(field) is not None:
            if doc.get(field) != data.get(field):
                doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        doc.save(ignore_permissions=True)

    return get_loan_security_type_by_id(doc.name)


def get_loan_security_type_by_id(type_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Security Type", type_id):
        raise frappe.DoesNotExistError(f"Loan Security Type '{type_id}' does not exist.")
        
    doc = frappe.get_doc("Loan Security Type", type_id)
    result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    
    return result


def get_loan_security_types(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []
    
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["loan_security_type", "like", search_term]
        ]

    safe_filters = build_loan_security_type_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Security Type`.`{sort_by}` {sort_order_clean}"

    types = frappe.get_all(
        "Loan Security Type",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_types = len(
        frappe.get_all(
            "Loan Security Type",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_types + page_size - 1) // page_size

    return types, total_types, total_pages


def delete_loan_security_type(type_id: str):
    if not frappe.db.exists("Loan Security Type", type_id):
        raise frappe.DoesNotExistError(f"Loan Security Type '{type_id}' does not exist.")
        
    docstatus = frappe.db.get_value("Loan Security Type", type_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete a submitted Loan Security Type '{type_id}'. Cancel it first.")

    frappe.delete_doc("Loan Security Type", type_id, ignore_permissions=True)


def toggle_loan_security_type_status(type_id: str, disable_flag: int):
    if not frappe.db.exists("Loan Security Type", type_id):
        raise frappe.DoesNotExistError(f"Loan Security Type '{type_id}' does not exist.")
    
    doc = frappe.get_doc("Loan Security Type", type_id)
    
    if doc.disabled == disable_flag:
        action = "disabled" if disable_flag == 1 else "enabled"
        raise frappe.ValidationError(f"Loan Security Type '{doc.loan_security_type}' is already {action}.")

    doc.disabled = disable_flag
    doc.save(ignore_permissions=True)
    
    return {
        "id": doc.name,
        "loan_security_type": doc.loan_security_type,
        "disabled": doc.disabled
    }