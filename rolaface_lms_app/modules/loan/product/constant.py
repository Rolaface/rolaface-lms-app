ALLOWED_LOAN_PRODUCT_FIELDS = {
    "product_code", "product_name", "rate_of_interest", "loan_category",
    "maximum_loan_amount", "penalty_interest_rate", "bpi_recovery_method",
    "bpi_treatment", "company", "cyclic_day_of_the_month", "repayment_date_on",
    "repayment_schedule_type", "no_interest_till_month_end",
    "days_past_due_threshold_for_npa", "is_term_loan", "validate_normal_repayment",
    "disabled", "collection_offset_sequence_for_standard_asset",
    "collection_offset_sequence_for_sub_standard_asset",
    "collection_offset_sequence_for_written_off_asset",
    "collection_offset_sequence_for_settlement_collection",
    "min_days_bw_disbursement_first_repayment", "excess_amount_acceptance_limit",
    "sanctioned_amount_tolerance_percentage", "write_off_amount",
    "grace_period_in_days", "amended_from", "disbursement_account",
    "payment_account", "subsidy_adjustment_account", "loan_account",
    "security_deposit_account", "suspense_collection_account",
    "customer_refund_account", "interest_income_account", "interest_accrued_account",
    "interest_waiver_account", "interest_receivable_account", "suspense_interest_income",
    "broken_period_interest_recovery_account", "same_as_regular_interest_accounts",
    "additional_interest_income", "additional_interest_accrued",
    "additional_interest_receivable", "additional_interest_suspense",
    "additional_interest_waiver", "penalty_income_account", "penalty_accrued_account",
    "penalty_waiver_account", "penalty_receivable_account", "penalty_suspense_account",
    "write_off_account", "write_off_recovery_account"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "product_code", "product_name",
    "rate_of_interest", "maximum_loan_amount", "loan_category"
}

RETURN_FIELDS_GET_ALL = [
    "name", "product_code", "product_name", "loan_category",
    "rate_of_interest", "maximum_loan_amount", "disabled", "company"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_PRODUCT_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]