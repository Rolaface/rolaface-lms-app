DOCTYPE = "Custom Investor Flow"

REPAYMENT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

DEFAULT_STATUS = "Draft"
STATUS_RECEIVED = "Received"
STATUS_MATURED = "Matured"
STATUS_RENEWED = "Renewed"

# action (query param) -> Status value. Received is set only by receive_payment
# (it posts the Journal Entry); Matured / Renewed only by the maturity APIs.
STATUS_ACTION_MAP = {
    "approved": "Approved",
    "cancelled": "Cancelled",
}

# Status -> the statuses it can move to.
ALLOWED_STATUS_TRANSITIONS = {
    "Draft": ["Approved", "Cancelled"],
    "Approved": ["Received", "Cancelled"],
    "Received": ["Matured", "Renewed"],
    "Cancelled": [],
    "Matured": [],
    "Renewed": [],
}

# Custom Investor Settings (Single): the GL accounts used by the Investor Flow entries.
SETTINGS_DOCTYPE = "Custom Investor Settings"
SETTINGS_ACCOUNT_FIELDS = {
    "company_bank_account": "Company Bank Account",
    "investor_deposit_account": "Investor Deposit Account",
    "interest_payable_account": "Interest Payable Account",
    "interest_expense_account": "Interest Expense Account",
    "penalty_expense_account": "Penalty Expense Account",
}

# Status of a schedule row (Custom Investor Earning Schedule).
ROW_STATUS_PENDING = "Pending"
ROW_STATUS_ACCRUED = "Accrued"
ROW_STATUS_PAID = "Paid"

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

# Sent to receive_payment. paid_from = the investor's Bank Account (reference only).
PAYMENT_INPUT_FIELDS = ["payment_date", "ref_no", "payment_mode", "amount_paid", "paid_from"]

# Saved by receive_payment. paid_to = Company Bank Account from Custom Investor Settings.
PAYMENT_FIELDS = PAYMENT_INPUT_FIELDS + ["paid_to"]

# Set by receive_payment: paid_gl = Paid From Bank Account's Company Account, to_gl = paid_to.
# receive_entry = the Journal Entry; renewed_to / renewed_from link a renewal.
PAYMENT_GL_FIELDS = ["paid_gl", "to_gl", "receive_entry", "renewed_to", "renewed_from"]

RETURN_FIELDS_BANK_ACCOUNT = [
    "name", "account_name", "bank", "bank_account_no", "iban", "branch_code",
    "is_default", "account"
]

RETURN_FIELDS_GET_ALL = [
    "name", "investor", "investment_product", "investment_amount",
    "repayment_frequency", "maturity_date", "interest_rate",
    "first_repayment_date", "penalty_rate", "status", "contract_status", "renewed_from"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTOR_FLOW_FIELDS) + PAYMENT_FIELDS + PAYMENT_GL_FIELDS + [
    "name", "status", "contract_status", "mail_sent", "subject", "message", "creation", "modified"
]

# Earning & Settlement tab: detail fields and the "schedule" table (Custom Investor Earning Schedule).
SCHEDULE_TABLE_FIELD = "schedule"
EARNING_DETAIL_FIELDS = [
    "amount_invested", "frequency", "mat_date", "rate_of_interest", "first_repay_date", "rate_of_penalty"
]
EARNING_SCHEDULE_ROW_FIELDS = [
    "payment_date", "principal_amount", "interest_amount", "penalty_amount", "total_payment"
]
EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS = ["status", "accrual_entry", "payout_entry"]
EARNING_AMOUNT_FIELDS = ["principal_amount", "interest_amount", "penalty_amount", "total_payment"]

RETURN_FIELDS_EARNINGS_LIST = [
    "name", "investor", "investment_product", "amount_invested", "rate_of_interest",
    "frequency", "first_repay_date", "mat_date", "payment_date", "status"
]
# Statuses that have earnings (shown on the Earnings & Statements screen).
EARNING_STATUSES = ["Received", "Matured", "Renewed"]
