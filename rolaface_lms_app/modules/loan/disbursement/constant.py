ALLOWED_DISBURSEMENT_FIELDS = {
    "against_loan", "sanctioned_loan_amount", "current_disbursed_amount",
    "posting_date", "applicant_type", "loan_product", "monthly_repayment_amount",
    "loan_partner", "company", "applicant", "repayment_schedule_type",
    "repayment_frequency", "repayment_method", "tenure", "repayment_start_date",
    "is_term_loan", "withhold_security_deposit", "is_imported", "disbursement_date",
    "clearance_date", "bpi_difference_date", "broken_period_interest_days",
    "disbursed_amount", "broken_period_interest", "bpi_amount_difference",
    "principal_amount_paid", "mode_of_payment", "disbursement_account",
    "refund_account", "loan_account", "bank_account", "cost_center",
    "total_emi_charges", "reference_date", "days_past_due", "status",
    "reference_number", "amended_from", "tranche_number", "_comments"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "posting_date", "disbursed_amount", 
    "applicant", "status", "disbursement_date"
}

RETURN_FIELDS_GET_ALL = [
    "name", "against_loan", "applicant", "loan_product", 
    "disbursed_amount", "status", "posting_date", "company"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_DISBURSEMENT_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]