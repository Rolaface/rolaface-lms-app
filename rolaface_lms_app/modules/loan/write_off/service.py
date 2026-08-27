import frappe
from typing import Tuple, Dict, Any
from .utils import build_loan_write_off_filters, validate_loan_write_off_payload
from .constant import ALLOWED_WRITE_OFF_FIELDS, RETURN_FIELDS_GET_ALL, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS

def create_loan_write_off(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("company"):
        data["company"] = frappe.defaults.get_user_default("Company")
        
    validate_loan_write_off_payload(data, is_update=False)

    write_off_doc = frappe.new_doc("Loan Write Off")
    
    for field in ALLOWED_WRITE_OFF_FIELDS:
        if field in data and data.get(field) is not None:
            write_off_doc.set(field, data.get(field))
            
    write_off_doc.set_missing_values()    
    write_off_doc.insert(ignore_permissions=True)
    comment = data.get("_comments")
    if comment:
        write_off_doc.add_comment("Comment", text=str(comment))
    
    return get_loan_write_off_by_id(write_off_doc.name)


def update_loan_write_off(write_off_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Write Off", write_off_id):
        raise frappe.DoesNotExistError(f"Loan Write Off '{write_off_id}' does not exist.")

    write_off_doc = frappe.get_doc("Loan Write Off", write_off_id)
    
    if write_off_doc.docstatus == 1:
        raise frappe.ValidationError(f"Cannot update submitted Loan Write Off '{write_off_id}'.")

    validate_loan_write_off_payload(data, is_update=True)
    has_changes = False

    for field in ALLOWED_WRITE_OFF_FIELDS:
        if field in data and data.get(field) is not None:
            if write_off_doc.get(field) != data.get(field):
                write_off_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        write_off_doc.save(ignore_permissions=True)

    comment = data.get("_comments")
    if comment:
        write_off_doc.add_comment("Comment", text=str(comment))

    return get_loan_write_off_by_id(write_off_doc.name)


def get_loan_write_off_by_id(write_off_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Write Off", write_off_id):
        raise frappe.DoesNotExistError(f"Loan Write Off '{write_off_id}' does not exist.")
        
    write_off_doc = frappe.get_doc("Loan Write Off", write_off_id)
    return {field: write_off_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}


def get_loan_write_offs(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []
    
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["loan", "like", search_term],
            ["applicant", "like", search_term]
        ]

    safe_filters = build_loan_write_off_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Write Off`.`{sort_by}` {sort_order_clean}"

    write_offs = frappe.get_all(
        "Loan Write Off",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_write_offs = len(
        frappe.get_all(
            "Loan Write Off",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_write_offs + page_size - 1) // page_size

    return write_offs, total_write_offs, total_pages


def delete_loan_write_off(write_off_id: str):
    if not frappe.db.exists("Loan Write Off", write_off_id):
        raise frappe.DoesNotExistError(f"Loan Write Off '{write_off_id}' does not exist.")
        
    docstatus = frappe.db.get_value("Loan Write Off", write_off_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete a submitted Loan Write Off '{write_off_id}'. Cancel it first.")

    frappe.delete_doc("Loan Write Off", write_off_id, ignore_permissions=True)


def process_approval(write_off_doc):
    if write_off_doc.docstatus == 1:
        raise frappe.ValidationError("Loan Write Off is already submitted/approved.")
    if write_off_doc.docstatus == 2:
        raise frappe.ValidationError("Cannot approve a cancelled Loan Write Off. Please amend it first.")

    write_off_doc.submit()
    return {
        "id": write_off_doc.name,
        "docstatus": write_off_doc.docstatus
    }

def process_cancellation(write_off_doc):
    if write_off_doc.docstatus == 2:
        raise frappe.ValidationError("Loan Write Off is already cancelled.")
    if write_off_doc.docstatus == 0:
        raise frappe.ValidationError("Cannot cancel a Draft Loan Write Off. Submit it first.")

    write_off_doc.cancel()
    return {
        "id": write_off_doc.name,
        "docstatus": write_off_doc.docstatus
    }

def process_amendment(write_off_doc):
    if write_off_doc.docstatus == 0:
        raise frappe.ValidationError("Loan Write Off is already in Draft state.")
    if write_off_doc.docstatus == 1:
        raise frappe.ValidationError("Cannot amend an approved Loan Write Off. Cancel it first.")

    amended_doc = frappe.copy_doc(write_off_doc)
    amended_doc.amended_from = write_off_doc.name
    amended_doc.docstatus = 0
    amended_doc.insert()

    return {
        "id": amended_doc.name,
        "docstatus": amended_doc.docstatus,
        "amended_from": amended_doc.amended_from
    }

def update_loan_write_off_status(write_off_id: str, action: str):
    write_off_doc = frappe.get_doc("Loan Write Off", write_off_id)

    if not frappe.has_permission("Loan Write Off", "write", write_off_doc):
        raise frappe.PermissionError("No permission to modify this Loan Write Off.")

    if action == "approved":
        return process_approval(write_off_doc)
    elif action == "cancelled":
        return process_cancellation(write_off_doc)
    elif action == "amend":
        return process_amendment(write_off_doc)
    else:
        raise frappe.ValidationError("Invalid action. Allowed: approved, cancelled, amend")