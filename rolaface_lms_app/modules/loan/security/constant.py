ALLOWED_LOAN_SECURITY_FIELDS = {
    "loan_security_code", "loan_security_name", "haircut", 
    "original_security_value", "utilized_security_value", 
    "loan_security_type", "available_security_value", 
    "loan_to_value_ratio", "disabled"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "loan_security_code", 
    "original_security_value", "available_security_value", "disabled"
}

RETURN_FIELDS_GET_ALL = [
    "name", "loan_security_code", "loan_security_name", 
    "loan_security_type", "original_security_value", 
    "available_security_value", "disabled"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_SECURITY_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]