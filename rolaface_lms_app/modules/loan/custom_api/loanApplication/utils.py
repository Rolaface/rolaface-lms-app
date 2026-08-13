import frappe
from typing import Dict, Any


def validate_custom_loan_application_payload(data: Dict[str, Any], is_update: bool = False):
    if not is_update:
        if not data.get("application_type"):
            raise frappe.ValidationError("Application Type is required.")

        if data.get("application_type") == "Personal Loan":
            required_fields = [
                "first_name", "last_name", "phone", "email",
                "national_registration_card", "gender", "marital_status", "birth_date",
                "residential_address", "occupation", "employer_name", "nationality",
                "loan_purpose", "next_of_kin_name", "next_of_kin_phone",
                "next_of_kin_email", "next_of_kin_relationship",
            ]
        elif data.get("application_type") == "Business Loan":
            required_fields = [
                "company_name", "type_of_business", "established_date",
                "nature_of_business", "registered_office", "collateral_pledged",
                "purpose_of_loan", "applicant_first_name", "applicant_last_name",
                "applicant_phone", "applicant_email", "applicant_national_registration_card",
                "applicant_gender", "applicant_marital_status", "applicant_birth_date",
                "applicant_address", "applicant_position", "applicant_nationality",
            ]
        else:
            raise frappe.ValidationError("Invalid Application Type. Allowed: Personal Loan, Business Loan")

        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise frappe.ValidationError(f"Missing required fields: {', '.join(missing)}")

    if data.get("email"):
        frappe.utils.validate_email_address(data.get("email"), throw=True)

    if data.get("applicant_email"):
        frappe.utils.validate_email_address(data.get("applicant_email"), throw=True)

    if data.get("next_of_kin_email"):
        frappe.utils.validate_email_address(data.get("next_of_kin_email"), throw=True)


def sync_custom_loan_application_documents(loan_application, documents_data):
    if documents_data is None:
        return False

    loan_application.set("documents", [])
    for row in documents_data:
        loan_application.append("documents", {
            "document_name": row.get("document_name"),
            "file": row.get("file"),
        })
    return True


def sync_custom_loan_application_directors(loan_application, directors_data):
    if directors_data is None:
        return False

    loan_application.set("directors", [])
    for row in directors_data:
        loan_application.append("directors", {
            "director_name": row.get("director_name"),
            "director_phone": row.get("director_phone"),
            "director_email": row.get("director_email"),
            "national_registration_card": row.get("national_registration_card"),
        })
    return True


def sync_custom_loan_application_business_documents(loan_application, business_documents_data):
    if business_documents_data is None:
        return False

    loan_application.set("business_documents", [])
    for row in business_documents_data:
        loan_application.append("business_documents", {
            "document_name": row.get("document_name"),
            "file": row.get("file"),
            "document_for": row.get("document_for"),
        })
    return True

def build_custom_loan_application_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("status"):
        filters["status"] = args.get("status")

    if args.get("application_type"):
        filters["application_type"] = args.get("application_type")

    if args.get("customer"):
        filters["customer"] = args.get("customer")

    return filters