ALLOWED_RESTRUCTURE_FIELD = [
    "applicant_type", "applicant", "restructure_type", "loan_product",
    "loan", "restructure_date", "reason_for_restructure", "new_repayment_period_in_months",
    "new_rate_of_interest","_comments"
]

ALLOWED_CHARGE_FIELDS = [
    "charge", "is_post_restructure_charge", "restructure_charge_amount",
]

RETURN_GET_FIELD_BY_ID = list(ALLOWED_RESTRUCTURE_FIELD) + [
    "name","loan_restructure_charges","old_rate_of_interest", "old_loan_amount", "old_tenure"
]

GET_FIELDS = ["name", "restructure_type", "reason_for_restructure", "restructure_date", "status", "docstatus"]