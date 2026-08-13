import frappe
from typing import Dict, Tuple, Any
from .utils import (
    validate_custom_loan_application_payload,
    sync_custom_loan_application_documents,
    sync_custom_loan_application_directors,
    sync_custom_loan_application_business_documents,
    build_custom_loan_application_filters,
)
from .constants import ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS, RETURN_FIELDS_GET_ALL


def create_custom_loan_application(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_custom_loan_application_payload(data, is_update=False)

    loan_application = frappe.new_doc("Custom Loan Application")

    for field in ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS:
        if field in data and data.get(field) is not None:
            loan_application.set(field, data.get(field))

    sync_custom_loan_application_documents(loan_application, data.get("documents"))
    sync_custom_loan_application_directors(loan_application, data.get("directors"))
    sync_custom_loan_application_business_documents(loan_application, data.get("business_documents"))

    loan_application.insert(ignore_permissions=True)
    return get_custom_loan_application_by_id(loan_application.name)


def get_custom_loan_application_by_id(loan_application_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Custom Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Custom Loan Application '{loan_application_id}' does not exist.")

    doc = frappe.get_doc("Custom Loan Application", loan_application_id)
    result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    documents = []
    for row in doc.get("documents", []) or []:
        documents.append({
            "name": row.name,
            "document_name": row.document_name,
            "file": row.file,
        })
    result["documents"] = documents

    directors = []
    for row in doc.get("directors", []) or []:
        directors.append({
            "name": row.name,
            "director_name": row.director_name,
            "director_phone": row.director_phone,
            "director_email": row.director_email,
            "national_registration_card": row.national_registration_card,
        })
    result["directors"] = directors

    business_documents = []
    for row in doc.get("business_documents", []) or []:
        business_documents.append({
            "name": row.name,
            "document_name": row.document_name,
            "file": row.file,
            "document_for": row.document_for,
        })
    result["business_documents"] = business_documents

    return result

def get_custom_loan_applications(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["first_name", "like", search_term],
            ["last_name", "like", search_term],
            ["company_name", "like", search_term],
        ]

    safe_filters = build_custom_loan_application_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabCustom Loan Application`.`{sort_by}` {sort_order_clean}"

    loan_applications = frappe.get_all(
        "Custom Loan Application",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total = len(
        frappe.get_all(
            "Custom Loan Application",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total + page_size - 1) // page_size

    return loan_applications, total, total_pages

