DOCTYPE = "Custom Investment Product"

PAYOUT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

# Product code: set once on create (unique, saved in UPPERCASE), never changed afterwards.
PRODUCT_CODE_FIELD = "product_code"

ALLOWED_INVESTMENT_PRODUCT_FIELDS = {
    "product_code", "product_name", "product_description",
    "default_tenure", "default_interest_rate", "default_penalty_rate", "payout_frequency", "disabled",
    "min_interest_rate", "maximum_interest_rate",
    "minimum_investment", "maximum_investment",
    "minimum_tenure", "maximum_tenure",
}

REQUIRED_FIELDS = [
    "product_code", "product_name", "product_description",
    "default_tenure", "default_interest_rate", "payout_frequency",
    "min_interest_rate", "maximum_interest_rate",
    "minimum_investment", "maximum_investment",
    "minimum_tenure", "maximum_tenure",
]

# field -> label, used in validation messages.
FIELD_LABELS = {
    "product_code": "Product Code",
    "product_name": "Product Name",
    "product_description": "Product Description",
    "default_tenure": "Default Tenure",
    "default_interest_rate": "Default Interest Rate",
    "default_penalty_rate": "Default Penalty Rate",
    "payout_frequency": "Default Payout Frequency",
    "min_interest_rate": "Minimum Interest Rate",
    "maximum_interest_rate": "Maximum Interest Rate",
    "minimum_investment": "Minimum Investment",
    "maximum_investment": "Maximum Investment",
    "minimum_tenure": "Minimum Tenure",
    "maximum_tenure": "Maximum Tenure",
}

PERCENT_FIELDS = ["default_interest_rate", "default_penalty_rate", "min_interest_rate", "maximum_interest_rate"]
AMOUNT_FIELDS = ["minimum_investment", "maximum_investment"]
TENURE_FIELDS = ["default_tenure", "minimum_tenure", "maximum_tenure"]

# (minimum field, maximum field) pairs: minimum must not be above maximum.
LIMIT_PAIRS = [
    ("min_interest_rate", "maximum_interest_rate"),
    ("minimum_investment", "maximum_investment"),
    ("minimum_tenure", "maximum_tenure"),
]

# Default field -> (minimum field, maximum field) it must stay within.
DEFAULT_WITHIN_LIMITS = {
    "default_interest_rate": ("min_interest_rate", "maximum_interest_rate"),
    "default_tenure": ("minimum_tenure", "maximum_tenure"),
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "product_code", "product_name", "payout_frequency",
    "default_tenure", "default_interest_rate", "minimum_investment", "maximum_investment",
}

RETURN_FIELDS_GET_ALL = ["name"] + sorted(ALLOWED_INVESTMENT_PRODUCT_FIELDS)

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTMENT_PRODUCT_FIELDS) + [
    "name", "creation", "modified"
]
