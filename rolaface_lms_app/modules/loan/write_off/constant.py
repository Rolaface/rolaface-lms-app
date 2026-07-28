ALLOWED_WRITE_OFF_FIELDS = {
    "loan", "loan_disbursement", "applicant_type", "applicant", 
    "loan_product", "company", "posting_date", "value_date", 
    "is_npa", "is_settlement_write_off", "cost_center", 
    "write_off_account", "write_off_amount", "amended_from"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "posting_date", 
    "value_date", "write_off_amount", "applicant"
}

RETURN_FIELDS_GET_ALL = [
    "name", "loan", "applicant", "loan_product", 
    "write_off_amount", "posting_date", "company", "docstatus"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_WRITE_OFF_FIELDS) + [
    "name", "creation", "modified", "docstatus", "owner"
]