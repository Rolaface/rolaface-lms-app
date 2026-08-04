ALLOWED_LOAN_SECURITY_FIELDS = {
    "loan_security_code", "loan_security_type", "loan_security_name",
    "loan_to_value_ratio", "haircut", "disabled", "original_security_value"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "loan_security_code", "loan_security_name",
    "loan_security_type", "original_security_value"
}

RETURN_FIELDS_GET_ALL = [
    "name", "loan_security_code", "loan_security_name", "loan_security_type",
    "loan_to_value_ratio", "haircut", "disabled", "original_security_value"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_SECURITY_FIELDS) + [
    "name", "creation", "modified"
]