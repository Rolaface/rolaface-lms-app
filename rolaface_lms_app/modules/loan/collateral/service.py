import frappe
from typing import Tuple, Dict, Any
from .constant import (
    ALLOWED_LOAN_SECURITY_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
)
from .utils import _validate_loan_security_payload, _build_loan_security_filters

def create_loan_security(data: Dict[str, Any]) -> Dict[str, Any]:
    _validate_loan_security_payload(data, is_update=False)

    if frappe.db.exists("Loan Security", data.get("loan_security_code")):
        raise frappe.DuplicateEntryError(f"Loan Security '{data.get('loan_security_code')}' already exists.")

    loan_security_doc = frappe.new_doc("Loan Security")

    for field in ALLOWED_LOAN_SECURITY_FIELDS:
        if field in data and data.get(field) is not None:
            loan_security_doc.set(field, data.get(field))

    loan_security_doc.insert(ignore_permissions=True)
    return get_loan_security_by_id(loan_security_doc.name)


def update_loan_security(loan_security_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Security", loan_security_id):
        raise frappe.DoesNotExistError(f"Loan Security '{loan_security_id}' does not exist.")

    loan_security_doc = frappe.get_doc("Loan Security", loan_security_id)

    _validate_loan_security_payload(data, is_update=True)
    has_changes = False

    for field in ALLOWED_LOAN_SECURITY_FIELDS:
        if field in data and data.get(field) is not None:
            if loan_security_doc.get(field) != data.get(field):
                loan_security_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        loan_security_doc.save(ignore_permissions=True)

    return get_loan_security_by_id(loan_security_doc.name)


def get_loan_security_by_id(loan_security_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Security", loan_security_id):
        raise frappe.DoesNotExistError(f"Loan Security '{loan_security_id}' does not exist.")

    loan_security_doc = frappe.get_doc("Loan Security", loan_security_id)
    result = {field: loan_security_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    return result


def get_loan_securities(
    args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc"
) -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["loan_security_code", "like", search_term],
            ["loan_security_name", "like", search_term],
        ]

    safe_filters = _build_loan_security_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Security`.`{sort_by}` {sort_order_clean}"

    loan_securities = frappe.get_all(
        "Loan Security",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_records = len(
        frappe.get_all(
            "Loan Security",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_records + page_size - 1) // page_size

    return loan_securities, total_records, total_pages


def delete_loan_security(loan_security_id: str):
    if not frappe.db.exists("Loan Security", loan_security_id):
        raise frappe.DoesNotExistError(f"Loan Security '{loan_security_id}' does not exist.")

    frappe.delete_doc("Loan Security", loan_security_id, ignore_permissions=True)

def toggle_loan_security_status(loan_security_id: str, disable_flag: int):
    if not frappe.db.exists("Loan Security", loan_security_id):
        raise frappe.DoesNotExistError(f"Loan Security '{loan_security_id}' does not exist.")
 
    loan_security_doc = frappe.get_doc("Loan Security", loan_security_id)
 
    if loan_security_doc.disabled == disable_flag:
        action = "disabled" if disable_flag == 1 else "enabled"
        raise frappe.ValidationError(
            f"Loan Security '{loan_security_doc.loan_security_name}' is already {action}."
        )
 
    loan_security_doc.disabled = disable_flag
    loan_security_doc.save(ignore_permissions=True)
 
    return {
        "id": loan_security_doc.name,
        "loan_security_code": loan_security_doc.loan_security_code,
        "loan_security_name": loan_security_doc.loan_security_name,
        "disabled": loan_security_doc.disabled
    }