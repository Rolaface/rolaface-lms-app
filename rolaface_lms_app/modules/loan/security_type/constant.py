ALLOWED_LOAN_SECURITY_TYPE_FIELDS = {
    "loan_security_type", "haircut", "loan_to_value_ratio", "disabled"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "loan_security_type", "disabled"
}

RETURN_FIELDS_GET_ALL = [
    "name", "loan_security_type", "haircut", 
    "loan_to_value_ratio", "disabled"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_SECURITY_TYPE_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]