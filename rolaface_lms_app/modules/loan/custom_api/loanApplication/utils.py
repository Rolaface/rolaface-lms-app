import frappe
from typing import Dict, Any
from .constants import CUSTOMER_GROUP, TERRITORY

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

def create_customer_from_application(application) -> str:
    if application.application_type == "Personal Loan":
        customer_name = " ".join(
            part for part in [application.first_name, application.middle_name, application.last_name] if part
        )
        mobile_no = application.phone
        email_id = application.email
        customer_type = "Individual"
    elif application.application_type == "Business Loan":
        customer_name = application.company_name
        mobile_no = application.applicant_phone
        email_id = application.applicant_email
        customer_type = "Company"
    else:
        raise frappe.ValidationError(
            f"Cannot create Customer for application_type '{application.application_type}'."
        )

    if not customer_name:
        raise frappe.ValidationError("Cannot create Customer: applicant name is missing on the application.")

    customer = frappe.new_doc("Customer")
    customer.customer_name = customer_name
    customer.customer_type = customer_type
    customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
    if not customer_group:
        raise frappe.ValidationError("No non-group Customer Group exists in the system to assign to the new Customer.")
    if not territory:
        raise frappe.ValidationError("No non-group Territory exists in the system to assign to the new Customer.")
    customer.customer_group = customer_group
    customer.territory = territory
    customer.mobile_no = mobile_no
    customer.email_id = email_id
    customer.insert(ignore_permissions=True)

    return customer.name