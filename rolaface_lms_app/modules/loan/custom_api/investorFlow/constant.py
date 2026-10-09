DOCTYPE = "Custom Investor Flow"

REPAYMENT_FREQUENCIES = ["Monthly", "Weekly", "Bi-Weekly", "Quarterly", "Yearly"]

DEFAULT_STATUS = "Draft"
STATUS_APPROVED = "Approved"
# Set by record_fund when the full contract amount has been received.
STATUS_PAID = "Paid"
# Earlier statuses; Earnings / Maturity still use them and are reworked in a later step.
STATUS_RECEIVED = "Received"
STATUS_MATURED = "Matured"
STATUS_RENEWED = "Renewed"

# action (query param) -> Status value. Paid is set only by record_fund (it posts the Journal Entries).
STATUS_ACTION_MAP = {
    "approved": "Approved",
    "cancelled": "Cancelled",
}

# Fund Status: what has been received against the contract's Investment Amount.
FUND_STATUS_PENDING = "Pending"
FUND_STATUS_PARTIAL = "Partial"
FUND_STATUS_PAID = "Paid"

# Record Fund screen: approved investments, until and after they are fully funded.
FUND_LIST_STATUSES = ["Approved", "Paid"]

# Child table of received funds (Custom Investor Record Fund).
FUND_TABLE_FIELD = "details"
FUND_RECORD_DOCTYPE = "Custom Investor Record Fund"

# Record Status of each fund record: Draft (no accounting) -> Approved (Journal Entry posted) / Cancelled.
RECORD_STATUS_DRAFT = "Draft"
RECORD_STATUS_APPROVED = "Approved"
RECORD_STATUS_CANCELLED = "Cancelled"

# Mode of Payment -> the Custom Investor Settings field with the GL that is debited (where the money lands).
PAYMENT_MODE_ACCOUNT_FIELDS = {
    "Cash": "investor_cash_account",
    "Cheque": "cheque_account",
    "Bank Draft": "bank_draft_account",
    "Wire Transfer": "wire_transfer_account",
}

# Only these can be deleted (no money has moved and no Journal Entry exists).
DELETABLE_STATUSES = ["Draft", "Cancelled"]

# Status -> the statuses it can move to.
ALLOWED_STATUS_TRANSITIONS = {
    "Draft": ["Approved", "Cancelled"],
    "Approved": ["Paid", "Cancelled"],
    "Paid": [],
    "Received": ["Matured", "Renewed"],
    "Cancelled": [],
    "Matured": [],
    "Renewed": [],
}

# Custom Investor Settings (Single): the GL accounts used by the Investor Flow entries.
SETTINGS_DOCTYPE = "Custom Investor Settings"
SETTINGS_ACCOUNT_FIELDS = {
    "investor_creditor_account": "Investor Creditor GL",
    "investor_cash_account": "Cash GL",
    "cheque_account": "Cheque GL",
    "bank_draft_account": "Bank Draft GL",
    "wire_transfer_account": "Wire Transfer GL",
    "company_bank_account": "Company Bank Account",
    "interest_payable_account": "Payable GL (Investor Payable)",
    "interest_expense_account": "Interest Expense GL",
    "penalty_expense_account": "Penalty Expense GL",
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


# Renewal links (set by the maturity Renew step).
RENEWAL_FIELDS = ["renewed_to", "renewed_from"]

RETURN_FIELDS_BANK_ACCOUNT = [
    "name", "account_name", "bank", "bank_account_no", "iban", "branch_code",
    "is_default", "account"
]

RETURN_FIELDS_GET_ALL = [
    "name", "investor", "investment_product", "investment_amount",
    "repayment_frequency", "maturity_date", "interest_rate",
    "first_repayment_date", "penalty_rate", "status", "contract_status", "renewed_from"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_INVESTOR_FLOW_FIELDS) + RENEWAL_FIELDS + [
    "name", "status", "contract_status", "fund_status", "mail_sent", "subject", "message", "creation", "modified"
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

# Repayment Record details come from the approved contract's terms:
# detail key (as the screens use it) -> Custom Investor Flow term field.
CONTRACT_TERM_FIELDS = {
    "amount_invested": "investment_amount",
    "frequency": "repayment_frequency",
    "mat_date": "maturity_date",
    "rate_of_interest": "interest_rate",
    "first_repay_date": "first_repayment_date",
    "rate_of_penalty": "penalty_rate",
}

RETURN_FIELDS_EARNINGS_LIST = ["name", "investor", "investment_product", "status", "fund_status"] + [
    f"{term} as {key}" for key, term in CONTRACT_TERM_FIELDS.items()
]
# Fund Status of investments that have a repayment schedule (Repayment Record screen).
EARNING_FUND_STATUSES = ["Partial", "Paid"]
