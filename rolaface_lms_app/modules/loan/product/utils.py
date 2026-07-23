import frappe
from typing import Dict, Any
import json
from frappe.utils import flt, cint

# --- Constants ---

ALLOWED_LOAN_PRODUCT_FIELDS = {
    "product_code", "product_name", "rate_of_interest", "loan_category",
    "maximum_loan_amount", "penalty_interest_rate", "bpi_recovery_method",
    "bpi_treatment", "company", "cyclic_day_of_the_month", "repayment_date_on",
    "repayment_schedule_type", "no_interest_till_month_end",
    "days_past_due_threshold_for_npa", "is_term_loan", "validate_normal_repayment",
    "disabled", "collection_offset_sequence_for_standard_asset",
    "collection_offset_sequence_for_sub_standard_asset",
    "collection_offset_sequence_for_written_off_asset",
    "collection_offset_sequence_for_settlement_collection",
    "min_days_bw_disbursement_first_repayment", "excess_amount_acceptance_limit",
    "sanctioned_amount_tolerance_percentage", "write_off_amount",
    "grace_period_in_days", "amended_from", "disbursement_account",
    "payment_account", "subsidy_adjustment_account", "loan_account",
    "security_deposit_account", "suspense_collection_account",
    "customer_refund_account", "interest_income_account", "interest_accrued_account",
    "interest_waiver_account", "interest_receivable_account", "suspense_interest_income",
    "broken_period_interest_recovery_account", "same_as_regular_interest_accounts",
    "additional_interest_income", "additional_interest_accrued",
    "additional_interest_receivable", "additional_interest_suspense",
    "additional_interest_waiver", "penalty_income_account", "penalty_accrued_account",
    "penalty_waiver_account", "penalty_receivable_account", "penalty_suspense_account",
    "write_off_account", "write_off_recovery_account"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "product_code", "product_name",
    "rate_of_interest", "maximum_loan_amount", "loan_category"
}

RETURN_FIELDS_GET_ALL = [
    "name", "product_code", "product_name", "loan_category",
    "rate_of_interest", "maximum_loan_amount", "disabled", "company"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_PRODUCT_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]

# --- Validation Logic ---

def validate_loan_product_payload(data: Dict[str, Any], is_update=False):
    # Required Fields for Creation
    if not is_update:
        if not data.get("product_code"):
            raise frappe.ValidationError("product_code is required.")
        if not data.get("product_name"):
            raise frappe.ValidationError("product_name is required.")

    # Numeric Bounds Validation
    if "rate_of_interest" in data:
        if flt(data.get("rate_of_interest")) < 0:
            raise frappe.ValidationError("rate_of_interest cannot be negative.")
            
    if "maximum_loan_amount" in data:
        if flt(data.get("maximum_loan_amount")) < 0:
            raise frappe.ValidationError("maximum_loan_amount cannot be negative.")
            
    if "penalty_interest_rate" in data:
        if flt(data.get("penalty_interest_rate")) < 0:
            raise frappe.ValidationError("penalty_interest_rate cannot be negative.")

    # Validate Company
    company = data.get("company")
    if company and not frappe.db.exists("Company", company):
        raise frappe.ValidationError(f"Company '{company}' does not exist.")

    # Validate Accounts (Ensure they exist if provided)
    account_fields = [
        "disbursement_account", "payment_account", "loan_account", 
        "interest_income_account", "penalty_income_account"
    ]
    for acc_field in account_fields:
        acc = data.get(acc_field)
        if acc and not frappe.db.exists("Account", acc):
            raise frappe.ValidationError(f"Account '{acc}' provided for {acc_field} does not exist.")

    # Check for Duplicate Product Code / Name
    if data.get("product_code") or data.get("product_name"):
        or_filters = []
        if data.get("product_code"):
            or_filters.append(["product_code", "=", data["product_code"]])
        if data.get("product_name"):
            or_filters.append(["product_name", "=", data["product_name"]])
            
        filters = [["docstatus", "<", 2]]
        
        existing = frappe.get_all(
            "Loan Product",
            filters=filters,
            or_filters=or_filters,
            fields=["name", "product_code", "product_name"]
        )
        
        for ext in existing:
            if is_update and ext.name == data.get("name"):
                continue
            if ext.product_code == data.get("product_code"):
                raise frappe.DuplicateEntryError(f"Loan Product with Product Code '{data['product_code']}' already exists.")
            if ext.product_name == data.get("product_name"):
                raise frappe.DuplicateEntryError(f"Loan Product with Product Name '{data['product_name']}' already exists.")

# --- Filter Logic ---

def build_loan_product_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]

    if args.get("disabled") is not None:
        frappe_filters["disabled"] = cint(args["disabled"])

    if args.get("loan_category"):
        frappe_filters["loan_category"] = ["in", args["loan_category"]] if isinstance(args["loan_category"], list) else args["loan_category"]

    if args.get("is_term_loan") is not None:
        frappe_filters["is_term_loan"] = cint(args["is_term_loan"])

    minRate = args.get("minRate")
    maxRate = args.get("maxRate")
    if minRate and maxRate:
        frappe_filters["rate_of_interest"] = ["between", [flt(minRate), flt(maxRate)]]
    elif minRate:
        frappe_filters["rate_of_interest"] = [">=", flt(minRate)]
    elif maxRate:
        frappe_filters["rate_of_interest"] = ["<=", flt(maxRate)]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["maximum_loan_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["maximum_loan_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["maximum_loan_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters

# --- Error Handling ---

def handle_api_error(e: Exception, context_message: str):
    """
    Centralized error handler mapping exceptions to proper JSON responses.
    """
    frappe.db.rollback()
    
    # Only log traceback for unhandled core exceptions, not validation errors
    if not isinstance(e, (frappe.ValidationError, frappe.DuplicateEntryError, frappe.DoesNotExistError)):
        frappe.log_error(frappe.get_traceback(), context_message)

    error_message = str(e).strip()
    # Strip HTML tags if Frappe wrapped the exception
    import re
    error_message = re.sub('<[^<]+?>', '', error_message)

    status_code = 500
    status_type = "error"

    if isinstance(e, frappe.DoesNotExistError):
        status_code = 404
        status_type = "fail"
    elif isinstance(e, frappe.DuplicateEntryError):
        status_code = 409
        status_type = "fail"
    elif isinstance(e, frappe.PermissionError):
        status_code = 403
        status_type = "fail"
        error_message = "You do not have permission to perform this action."
    elif isinstance(e, frappe.ValidationError):
        status_code = 400
        status_type = "fail"

    from rolaface_lms_app.utils.api_response import send_response 
    
    return send_response(
        status=status_type,
        message=error_message,
        status_code=status_code,
        http_status=status_code,
    )