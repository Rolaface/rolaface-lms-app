ALLOWED_PAYMENT_FIELD = [
    "repayment_type", "applicant_type", "applicant", "loan_product",
    "against_loan", "value_date", "amount_paid", "mode_of_payment",
    "reference_number", "reference_date"
]

RETURN_FIELDS_GET_ALL = [
    "name", "repayment_type", "applicant_type", "applicant", "loan_product",
    "against_loan", "value_date", "amount_paid", "mode_of_payment",
    "reference_number", "reference_date", "docstatus", "creation"
]

RETURN_FIELDS_GET_BY_ID = [
    "name", "repayment_type", "applicant_type", "applicant", "loan_product",
    "against_loan", "value_date", "amount_paid", "mode_of_payment",
    "reference_number", "reference_date", "docstatus"
]

ALLOWED_SORT_FIELDS = [
    "name", "value_date", "amount_paid", "creation"
]