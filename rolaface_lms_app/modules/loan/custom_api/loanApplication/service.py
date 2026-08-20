import frappe
from typing import Dict, Tuple, Any
from .utils import (
    validate_custom_loan_application_payload,
    sync_custom_loan_application_documents,
    sync_custom_loan_application_directors,
    sync_custom_loan_application_business_documents,
    build_custom_loan_application_filters,
    create_customer_from_application,
)
from .constants import ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS, RETURN_FIELDS_GET_ALL, CONVERTIBLE_STATUS
from rolaface_lms_app.modules.loan.loan import service as loan_service

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

def convert_custom_loan_application_to_loan(loan_application_id: str, loan_product: str) -> Dict[str, Any]:
    company = frappe.defaults.get_user_default("Company")
    if not frappe.db.exists("Custom Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Custom Loan Application '{loan_application_id}' does not exist.")

    application = frappe.get_doc("Custom Loan Application", loan_application_id)

    if application.status != CONVERTIBLE_STATUS:
        raise frappe.ValidationError(
            f"Only applications with status '{CONVERTIBLE_STATUS}' can be converted. "
            f"Current status: '{application.status}'."
        )

    applicant = application.customer
    if not applicant:
        applicant = create_customer_from_application(application)
        frappe.db.set_value("Custom Loan Application", application.name, "customer", applicant)

    loan_payload = {
        "applicant_type": "Customer",
        "applicant": applicant,
        "loan_product": loan_product,
        "company": company,
        "loan_amount": application.amount,
        "posting_date": frappe.utils.nowdate(),
    }

    if application.tenure:
        loan_payload["repayment_periods"] = application.tenure
        loan_payload["repayment_method"] = "Repay Over Number of Periods"

    loan_data = loan_service.create_loan(loan_payload)

    loan_doc = frappe.get_doc("Loan", loan_data["name"])
    loan_doc.append("custom_loan_details", {
        "loan_application_number": application.name,
    })
    loan_doc.save(ignore_permissions=True)

    documents_payload = []
    for row in application.get("documents", []) or []:
        if row.get("file"):
            documents_payload.append(
                {"file_name": row.get("document_name"), "file_url": row.get("file")}
            )

    if application.application_type == "Business Loan":
        for row in application.get("business_documents", []) or []:
            if row.get("file"):
                documents_payload.append(
                    {"file_name": row.get("document_name"), "file_url": row.get("file")}
                )

    if documents_payload:
        loan_service.attach_loan_documents(loan_data["name"], documents_payload)

    return loan_service.get_loan_by_id(loan_data["name"])

def update_custom_loan_application(loan_application_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Custom Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Custom Loan Application '{loan_application_id}' does not exist.")

    loan_application = frappe.get_doc("Custom Loan Application", loan_application_id)

    validate_custom_loan_application_payload(data, is_update=True)

    for field in ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS:
        if field in data and data.get(field) is not None:
            loan_application.set(field, data.get(field))

    if "documents" in data:
        sync_custom_loan_application_documents(loan_application, data.get("documents"))

    if "directors" in data:
        sync_custom_loan_application_directors(loan_application, data.get("directors"))

    if "business_documents" in data:
        sync_custom_loan_application_business_documents(loan_application, data.get("business_documents"))

    loan_application.save(ignore_permissions=True)

    return get_custom_loan_application_by_id(loan_application.name)


def delete_custom_loan_application(loan_application_id: str):
    if not frappe.db.exists("Custom Loan Application", loan_application_id):
        raise frappe.DoesNotExistError(f"Custom Loan Application '{loan_application_id}' does not exist.")

    frappe.delete_doc("Custom Loan Application", loan_application_id, ignore_permissions=True)

def get_custom_loan_applications_by_nrc(national_registration_card: str) -> list:
    if not national_registration_card:
        raise frappe.ValidationError("National Registration Card is required.")

    matching_names = frappe.get_all(
        "Custom Loan Application",
        or_filters=[
            ["national_registration_card", "=", national_registration_card],
            ["applicant_national_registration_card", "=", national_registration_card],
        ],
        pluck="name",
    )

    if not matching_names:
        raise frappe.DoesNotExistError(
            f"No Custom Loan Application found for National Registration Card '{national_registration_card}'."
        )

    return [get_custom_loan_application_by_id(name) for name in matching_names]

def get_custom_loan_applications_by_email(email: str) -> list:
    if not email:
        raise frappe.ValidationError("Email is required.")

    matching_names = frappe.get_all(
        "Custom Loan Application",
        or_filters=[
            ["email", "=", email],
            ["applicant_email", "=", email],
        ],
        pluck="name",
    )

    if not matching_names:
        raise frappe.DoesNotExistError(
            f"No Custom Loan Application found for email '{email}'."
        )

    return [get_custom_loan_application_by_id(name) for name in matching_names]