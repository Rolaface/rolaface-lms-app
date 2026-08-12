ALLOWED_LOAN_APPLICATION_FIELDS = {
    "applicant_email_address", "applicant_phone_number",
    "applicant_name", "company", "posting_date", "status", "loan_purpose",
    "loan_product", "loan_amount", "rate_of_interest", "is_term_loan", "is_secured_loan",
    "repayment_method", "repayment_periods", "monthly_repayment_amount",
    "repayment_start_date", "country","address_line_1","address_line_2","city","state","zip_code",
    "amount", "tenure", "total_amount"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "posting_date", "loan_amount",
    "applicant", "status", "company"
}

RETURN_FIELDS_GET_ALL = [
    "name", "applicant_name", "applicant_email_address", "applicant_phone_number", "loan_product", "loan_amount", "status", "posting_date"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_APPLICATION_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]