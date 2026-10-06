DOCTYPE = "Custom Investment Product"

PAYOUT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

ALLOWED_INVESTMENT_PRODUCT_FIELDS = {
    "product_name", "tenure", "minimum_investment",
    "interest_rate", "payout_frequency", "disabled"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "product_name", "tenure",
    "minimum_investment", "interest_rate", "payout_frequency"
}

RETURN_FIELDS_GET_ALL = [
    "name", "product_name", "tenure", "minimum_investment",
    "interest_rate", "payout_frequency", "disabled"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTMENT_PRODUCT_FIELDS) + [
    "name", "creation", "modified"
]