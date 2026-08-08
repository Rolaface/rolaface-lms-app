import frappe
from typing import Dict, Any


def validate_loan_application_payload(data: Dict[str, Any], is_update: bool = False):
    if not is_update:
        required_fields = [
            "applicant_name", "applicant_email_address",
            "applicant_phone_number", "company", "posting_date", "loan_product",
            "repayment_method"
        ]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            raise frappe.ValidationError(f"Missing required fields: {', '.join(missing)}")

    if data.get("applicant_email_address"):
        frappe.utils.validate_email_address(data.get("applicant_email_address"), throw=True)

    if data.get("repayment_method") == "Repay Over Number of Periods" and not data.get("repayment_periods") and not is_update:
        raise frappe.ValidationError("Repayment Period in Months is required for this repayment method.")

    if data.get("repayment_method") == "Repay Fixed Amount per Period" and not data.get("monthly_repayment_amount") and not is_update:
        raise frappe.ValidationError("Monthly Repayment Amount is required for this repayment method.")


def build_loan_application_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}

    if args.get("status"):
        filters["status"] = args.get("status")

    if args.get("applicant"):
        filters["applicant"] = args.get("applicant")

    if args.get("company"):
        filters["company"] = args.get("company")

    if args.get("loan_product"):
        filters["loan_product"] = args.get("loan_product")

    if args.get("minAmount") or args.get("maxAmount"):
        min_amount = float(args.get("minAmount") or 0)
        max_amount = float(args.get("maxAmount") or 0) or None
        if max_amount:
            filters["loan_amount"] = ["between", [min_amount, max_amount]]
        else:
            filters["loan_amount"] = [">=", min_amount]

    return filters

def sync_loan_application_co_applicants(loan_application, co_applicants_data):
    if co_applicants_data is None:
        return False

    loan_application.set("co_applicants", [])
    for row in co_applicants_data:
        loan_application.append("co_applicants", {
            "applicant_name": row.get("applicant_name"),
            "applicant_email": row.get("applicant_email"),
            "applicant_mobile": row.get("applicant_mobile"),
        })
    return True


def sync_loan_application_documents(loan_application, documents_data):
    if documents_data is None:
        return False

    loan_application.set("documents", [])
    for row in documents_data:
        loan_application.append("documents", {
            "document_type": row.get("document_type"),
            "file": row.get("file"),
        })
    return True