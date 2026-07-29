ALLOWED_LOAN_FIELDS = {
    "applicant_type", "applicant", "applicant_name", "loan_application", "company",
    "posting_date", "status", "is_imported", "migration_date", 
    "auto_create_disbursement_on_loan_booking", "loan_product", "loan_amount",
    "loan_partner", "loan_category", "repayment_schedule_type", "no_interest_till_month_end",
    "cancellation_date", "settlement_date", "rate_of_interest", "penalty_charges_rate",
    "disbursement_date", "disbursed_amount", "closure_date", "maximum_loan_amount",
    "is_secured_loan", "is_term_loan", "repayment_start_date", "repayment_frequency",
    "monthly_repayment_amount", "repayment_method", "repayment_periods", "moratorium_type",
    "moratorium_tenure", "treatment_of_interest", "cost_center", "disbursement_account",
    "payment_account", "loan_account", "interest_income_account", "penalty_income_account", "branch"
}

ALLOWED_SORT_FIELDS = {
    "name", "creation", "modified", "posting_date", "loan_amount", 
    "applicant", "status", "disbursement_date"
}

RETURN_FIELDS_GET_ALL = [
    "name", "applicant_type", "applicant", "applicant_name", "loan_product", 
    "loan_amount", "branch", "rate_of_interest", "status", "posting_date"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_LOAN_FIELDS) + [
    "name", "creation", "modified", "docstatus", "total_payment", 
    "total_interest_payable", "total_principal_paid", "is_npa", "written_off_amount"
]