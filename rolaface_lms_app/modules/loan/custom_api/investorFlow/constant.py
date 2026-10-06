DOCTYPE = "Custom Investor Flow"

REPAYMENT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

DEFAULT_STATUS = "Draft"

# action (query param) -> Status value
STATUS_ACTION_MAP = {
    "approved": "Approved",
    "received": "Received",
    "cancelled": "Cancelled",
}

# Status -> the statuses it can move to. Received and Cancelled are final.
ALLOWED_STATUS_TRANSITIONS = {
    "Draft": ["Approved", "Cancelled"],
    "Approved": ["Received", "Cancelled"],
    "Received": [],
    "Cancelled": [],
}

ALLOWED_INVESTOR_FLOW_FIELDS = {
    "investor", "investment_product", "investment_amount", "repayment_frequency",
    "maturity_date", "interest_rate", "first_repayment_date", "penalty_rate"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "investor", "investment_product",
    "investment_amount", "interest_rate", "repayment_frequency",
    "first_repayment_date", "maturity_date", "status"
}

RETURN_FIELDS_GET_ALL = [
    "name", "investor", "investment_product", "investment_amount",
    "repayment_frequency", "maturity_date", "interest_rate",
    "first_repayment_date", "penalty_rate", "status"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTOR_FLOW_FIELDS) + [
    "name", "status", "creation", "modified"
]