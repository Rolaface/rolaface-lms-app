import frappe
from typing import Dict, Tuple, Any
from .utils import (
    build_loan_application_filters,
    validate_loan_application_payload,
    sync_loan_application_co_applicants,
    sync_loan_application_documents,
)
from .constant import (
    ALLOWED_LOAN_APPLICATION_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
)


def create_loan_application(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("company"):
        data["company"] = frappe.defaults.get_user_default("Company")

    validate_loan_application_payload(data, is_update=False)

    loan_application = frappe.new_doc("Loan Application")

    for field in ALLOWED_LOAN_APPLICATION_FIELDS:
        if field in data and data.get(field) is not None:
            loan_application.set(field, data.get(field))

    sync_loan_application_co_applicants(loan_application, data.get("co_applicants"))
    sync_loan_application_documents(loan_application, data.get("documents"))

    loan_application.insert(ignore_permissions=True)
    return get_loan_application_by_id(loan_application.name)


def update_loan_application(loan_application_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Loan Application '{loan_application_id}' does not exist.")

    loan_application = frappe.get_doc("Loan Application", loan_application_id)

    if loan_application.docstatus == 1:
        raise frappe.ValidationError(f"Cannot update submitted Loan Application '{loan_application_id}'.")

    validate_loan_application_payload(data, is_update=True)
    has_changes = False

    for field in ALLOWED_LOAN_APPLICATION_FIELDS:
        if field in data and data.get(field) is not None:
            if loan_application.get(field) != data.get(field):
                loan_application.set(field, data.get(field))
                has_changes = True

    if "co_applicants" in data:
        if sync_loan_application_co_applicants(loan_application, data.get("co_applicants")):
            has_changes = True

    if "documents" in data:
        if sync_loan_application_documents(loan_application, data.get("documents")):
            has_changes = True

    if has_changes:
        loan_application.save(ignore_permissions=True)

    return get_loan_application_by_id(loan_application.name)


def get_loan_application_by_id(loan_application_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Loan Application '{loan_application_id}' does not exist.")

    doc = frappe.get_doc("Loan Application", loan_application_id)
    result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    co_applicants = []
    for row in doc.get("co_applicants", []) or []:
        co_applicants.append({
            "name": row.name,
            "applicant_name": row.applicant_name,
            "applicant_email": row.applicant_email,
            "applicant_mobile": row.applicant_mobile,
        })
    result["co_applicants"] = co_applicants

    documents = []
    for row in doc.get("documents", []) or []:
        documents.append({
            "name": row.name,
            "document_type": row.document_type,
            "file": row.file,
        })
    result["documents"] = documents

    return result

def get_loan_applications(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["applicant", "like", search_term],
            ["applicant_email_address", "like", search_term],
        ]

    safe_filters = build_loan_application_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Application`.`{sort_by}` {sort_order_clean}"

    loan_applications = frappe.get_all(
        "Loan Application",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total = len(
        frappe.get_all(
            "Loan Application",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total + page_size - 1) // page_size

    return loan_applications, total, total_pages

def delete_loan_application(loan_application_id: str):
    if not frappe.db.exists("Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Loan Application '{loan_application_id}' does not exist.")

    docstatus = frappe.db.get_value("Loan Application", loan_application_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete a submitted Loan Application '{loan_application_id}'.")

    frappe.delete_doc("Loan Application", loan_application_id, ignore_permissions=True)


def update_loan_application_status(loan_application_id: str, action: str) -> Dict[str, Any]:
    loan_application = frappe.get_doc("Loan Application", loan_application_id)

    action_status_map = {
        "approved": "Approved",
        "rejected": "Rejected",
    }

    if action not in action_status_map:
        raise frappe.ValidationError("Invalid action. Allowed: approved, rejected")

    loan_application.status = action_status_map[action]
    loan_application.save(ignore_permissions=True)

    return {
        "id": loan_application.name,
        "status": loan_application.status,
    }