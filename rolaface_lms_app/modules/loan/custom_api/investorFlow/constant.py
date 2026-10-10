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

RETURN_FIELDS_EARNINGS_LIST = [
    "name", "investor", "investment_product", "status", "fund_status", "payment_status", "renewal_status",
] + [
    f"{term} as {key}" for key, term in CONTRACT_TERM_FIELDS.items()
]
# Fund Status of investments that have a repayment schedule (Repayment Record screen).
EARNING_FUND_STATUSES = ["Partial", "Paid"]

# ------------------------------- Renewal -------------------------------
# Payment Status of an investment (Custom Investor Flow.payment_status), kept up to date by
# renewal.refresh_payment_status (daily job + after every payout / renewal action).
PAYMENT_STATUS_PENDING = "Pending"    # schedule running, money still due before maturity
PAYMENT_STATUS_PAID = "Paid"          # every row of the current schedule is Paid
PAYMENT_STATUS_RENEWED = "Renewed"    # running under an approved renewal
PAYMENT_STATUS_EXPIRED = "Expired"    # today is after the maturity date and money is still due

# Renewal Status (Custom Investor Flow.renewal_status).
RENEWAL_STATUS_DRAFT = "Draft"
RENEWAL_STATUS_APPROVED = "Approved"
RENEWAL_STATUS_CANCELLED = "Cancelled"
RENEWAL_DELETABLE_STATUSES = [RENEWAL_STATUS_DRAFT, RENEWAL_STATUS_CANCELLED]

# Renewal Structure options.
RENEWAL_CAPITALIZATION = "Capitalization"
RENEWAL_PRINCIPAL_ROLLOVER = "Principal Rollover"
RENEWAL_EXTENDED_MATURITY = "Extended Maturity"
RENEWAL_PARTIAL_SETTLEMENT = "Partial Settlement"
RENEWAL_STRUCTURES = [
    RENEWAL_CAPITALIZATION, RENEWAL_PRINCIPAL_ROLLOVER, RENEWAL_EXTENDED_MATURITY, RENEWAL_PARTIAL_SETTLEMENT,
]
# Structures where the unpaid interest is not added to principal: it is paid now or deferred.
RENEWAL_INTEREST_SEPARATE = [RENEWAL_PRINCIPAL_ROLLOVER, RENEWAL_EXTENDED_MATURITY]

# Interest Settlement options (for RENEWAL_INTEREST_SEPARATE).
INTEREST_PAY_ON_RENEWAL = "Pay on renewal date"
INTEREST_DEFER = "Defer to an agreed future date"
INTEREST_SETTLEMENTS = [INTEREST_PAY_ON_RENEWAL, INTEREST_DEFER]

# Fields entered on the Renewal screen.
RENEWAL_INPUT_FIELDS = [
    "renewal_structure", "renewal_effective_date", "settlement_amount", "interest_settlement",
    "interest_settlement_date", "renewal_interest_rate", "payment_frequency", "renewal_tenure",
    "renewal_first_repayment_date", "renewal_penalty_rate", "reason_for_renewal",
]
# Calculated by the backend when the renewal is saved / approved.
RENEWAL_CALCULATED_FIELDS = [
    "renewed_principal", "new_maturity_date", "renewal_outstanding_principal", "renewal_unpaid_interest",
    "renewal_journal_entry", "renewal_status",
]
RENEWAL_MAIL_FIELDS = ["renewal_to", "renewal_subject", "renewal_message", "renewal_contract_status"]
RENEWAL_ALL_FIELDS = RENEWAL_INPUT_FIELDS + RENEWAL_CALCULATED_FIELDS + RENEWAL_MAIL_FIELDS
