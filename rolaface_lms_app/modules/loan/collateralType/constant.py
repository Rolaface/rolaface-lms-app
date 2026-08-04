ALLOWED_LOAN_SECURITY_TYPE_FIELDS = {
    "loan_security_type", "loan_to_value_ratio", "haircut", "disabled"
}

ALLOWED_SORT_FIELDS_TYPE = {
    "name", "creation", "modified", "loan_security_type", "loan_to_value_ratio", "haircut"
}

RETURN_FIELDS_GET_ALL_TYPE = [
    "name", "loan_security_type", "loan_to_value_ratio", "haircut", "disabled"
]

RETURN_FIELDS_GET_BY_ID_TYPE = list(ALLOWED_LOAN_SECURITY_TYPE_FIELDS) + [
    "name", "creation", "modified"
]