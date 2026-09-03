ROOT_FIELDS = {
    "name",
    "company",
    "enable_auto_disbursement",
    "enable_topup",
    # "creation",
    # "modified",
    # "docstatus"
}

ACCOUNT_CATEGORIES = {
    "principal_accounts": [
        "default_loan_account",
        "default_disbursement_bank_account",
        "default_repayment_bank_account"
    ],
    "interest_and_penalty_accounts": [
        "default_interest_income_account",
        "default_penalty_income_account",
        "default_interest_receivable_account",
        "default_penalty_receivable_account",
        "default_interest_accrued_account",
        "default_penalty_accrued_account",
        "default_interest_suspended_account",
        "default_penalty_suspended_account",
        "default_interest_waiver_account",
        "default_penalty_waiver_account",
        "same_as_interest"
    ],
    "general_accounts": [
        "default_write_off_account",
        "default_write_off_recovery",
        "default_subsidy_account",
        "default_security_deposit_account",
        "default_suspense_collection",
        "default_customer_refund"
    ]
}