FILTER_FIELD_MAP = {
    "company": "company",
    "branch": "branch",
    "loan_product": "loan_product",
    "customer": "applicant",
    "status": "status",
}

DOCTYPE_FILTER_FIELDS = {
    "Loan": {"company", "branch", "loan_product", "applicant", "status"},
    "Loan Application": {"company", "loan_product", "applicant", "status"},
    "Loan Disbursement": {"company", "branch", "loan_product", "applicant", "status"},
    "Loan Repayment": {"company", "branch", "loan_product", "applicant"},
}

PENDING_APPROVAL_STATUSES = ["Open"]

PAR_BUCKETS = [
    {"label": "30 Days", "min_days": 1, "max_days": 30},
    {"label": "60 Days", "min_days": 31, "max_days": 60},
    {"label": "90+ Days", "min_days": 61, "max_days": None},
]

RISK_GRADE_BUCKETS = [
    {"label": "Low Risk", "min_days": 0, "max_days": 30},
    {"label": "Medium Risk", "min_days": 31, "max_days": 60},
    {"label": "High Risk", "min_days": 61, "max_days": None},
]