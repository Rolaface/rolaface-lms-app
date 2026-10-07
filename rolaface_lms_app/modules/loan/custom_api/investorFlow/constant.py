DOCTYPE = "Custom Investor Flow"

REPAYMENT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

DEFAULT_STATUS = "Draft"
STATUS_RECEIVED = "Received"

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

CONTRACT_STATUS_PENDING = "Pending"
CONTRACT_STATUS_SENT = "Sent"
CONTRACT_STATUS_PAID = "Paid"

PAYMENT_MODES = ["Wire Transfer", "Cheque", "Cash", "Bank Draft"]

# Sent to receive_payment. paid_from = Bank Account, paid_to = Account.
PAYMENT_FIELDS = [
    "payment_date", "ref_no", "payment_mode", "amount_paid", "paid_from", "paid_to"
]

# Set by receive_payment: paid_gl = Paid From Bank Account's Company Account, to_gl = paid_to.
PAYMENT_GL_FIELDS = ["paid_gl", "to_gl"]

RETURN_FIELDS_BANK_ACCOUNT = [
    "name", "account_name", "bank", "bank_account_no", "iban", "branch_code",
    "is_default", "account"
]

RETURN_FIELDS_GET_ALL = [
    "name", "investor", "investment_product", "investment_amount",
    "repayment_frequency", "maturity_date", "interest_rate",
    "first_repayment_date", "penalty_rate", "status", "contract_status"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTOR_FLOW_FIELDS) + PAYMENT_FIELDS + PAYMENT_GL_FIELDS + [
    "name", "status", "contract_status", "mail_sent", "subject", "creation", "modified"
]

# Earning & Settlement tab: detail fields and the "schedule" table (Custom Investor Earning Schedule).
SCHEDULE_TABLE_FIELD = "schedule"
EARNING_DETAIL_FIELDS = [
    "amount_invested", "frequency", "mat_date", "rate_of_interest", "first_repay_date", "rate_of_penalty"
]
EARNING_SCHEDULE_ROW_FIELDS = [
    "payment_date", "principal_amount", "interest_amount", "penalty_amount", "total_payment"
]
EARNING_AMOUNT_FIELDS = ["principal_amount", "interest_amount", "penalty_amount", "total_payment"]

RETURN_FIELDS_EARNINGS_LIST = [
    "name", "investor", "investment_product", "amount_invested", "rate_of_interest",
    "frequency", "first_repay_date", "mat_date", "payment_date", "status"
]
