RULESET_DOCTYPE = "Custom LOS Prescreening Ruleset"
LOAN_PRODUCT_DOCTYPE = "Loan Product"

# ---------------------------------------------------------------- Status
STATUS_DRAFT = "Draft"
STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"
STATUS_ARCHIVED = "Archived"

# What set_ruleset_status accepts. Draft and Archived are reached through the lifecycle, not set directly.
SETTABLE_STATUSES = (STATUS_ACTIVE, STATUS_INACTIVE)

# The row the list screen shows for a product, best first.
LIST_STATUS_ORDER = (STATUS_ACTIVE, STATUS_INACTIVE, STATUS_DRAFT)

FIRST_VERSION = "1.0"

ALLOWED_UPDATE_FIELDS = {"ruleset_name", "description", "groups"}

RETURN_FIELDS = [
	"name",
	"ruleset_name",
	"loan_product",
	"description",
	"version",
	"status",
	"effective_from",
	"effective_to",
	"groups",
	"published_by",
	"published_on",
	"owner",
	"creation",
	"modified_by",
	"modified",
]

RULESET_NAME_MAX_LENGTH = 140

# ---------------------------------------------------------------- Rules
LOGICS = ("ALL", "ANY")
SEVERITIES = {
	"Blocking": "Reject Application",
	"Warning": "Continue with Warning",
	"Review": "Send for Manual Review",
}  # severity: default action
ACTIONS = ("Reject Application", "Mark as Ineligible", "Send for Manual Review", "Continue with Warning")
DATE_UNITS = ("days", "months", "years")

OPERATORS = {
	"numeric": (
		"equals",
		"not_equals",
		"greater_than",
		"greater_than_or_equal",
		"less_than",
		"less_than_or_equal",
		"between",
	),
	"text": ("equals", "not_equals", "contains", "starts_with", "in"),
	"dropdown": ("equals", "not_equals", "in", "not_in"),
	"boolean": ("equals",),
	"date": ("before", "after", "equals", "between", "older_than"),
}

# Same catalog as FIELDS in the frontend (PreScreening/types.tsx).
FIELDS = {
	"age": {"label": "Applicant Age", "category": "Applicant", "type": "numeric", "unit": "years"},
	"gender": {"label": "Gender", "category": "Applicant", "type": "dropdown", "options": ("Male", "Female", "Other")},
	"nationality": {"label": "Nationality", "category": "Applicant", "type": "dropdown", "options": ("Zambian", "Non-Zambian")},
	"customer_type": {"label": "Customer Type", "category": "Applicant", "type": "dropdown", "options": ("New Customer", "Existing Customer")},
	"location": {"label": "Applicant Location", "category": "Applicant", "type": "text"},
	"employment_status": {
		"label": "Employment Status",
		"category": "Employment",
		"type": "dropdown",
		"options": ("Permanent", "Contract", "Self Employed", "Temporary", "Unemployed"),
	},
	"employer": {"label": "Employer", "category": "Employment", "type": "text"},
	"employment_duration": {"label": "Employment Duration", "category": "Employment", "type": "numeric", "unit": "months"},
	"monthly_income": {"label": "Monthly Income", "category": "Employment", "type": "numeric", "unit": "ZMW"},
	"credit_score": {"label": "Credit Score", "category": "Credit", "type": "numeric", "unit": "pts"},
	"previous_defaults": {"label": "Number of Previous Defaults", "category": "Credit", "type": "numeric", "unit": "count"},
	"has_previous_default": {"label": "Has Previous Default", "category": "Credit", "type": "boolean"},
	"existing_loans": {"label": "Number of Active Loans", "category": "Credit", "type": "numeric", "unit": "count"},
	"has_existing_loan": {"label": "Has Existing Loan", "category": "Credit", "type": "boolean"},
	"overdue_amount": {"label": "Existing Overdue Amount", "category": "Credit", "type": "numeric", "unit": "ZMW"},
	"dti": {"label": "Debt-to-Income Ratio", "category": "Credit", "type": "numeric", "unit": "%"},
	"risk_category": {"label": "Customer Risk Category", "category": "Credit", "type": "dropdown", "options": ("Low", "Medium", "High")},
	"loan_amount": {"label": "Loan Amount", "category": "Loan", "type": "numeric", "unit": "ZMW"},
	"loan_purpose": {
		"label": "Loan Purpose",
		"category": "Loan",
		"type": "dropdown",
		"options": ("Personal", "Business", "Education", "Medical", "Home Improvement"),
	},
	"loan_tenure": {"label": "Loan Tenure", "category": "Loan", "type": "numeric", "unit": "months"},
	"customer_since": {"label": "Customer Since", "category": "Other", "type": "date"},
	"dob": {"label": "Date of Birth", "category": "Other", "type": "date"},
}

# ---------------------------------------------------------------- Test / evaluation result
VERDICT_ELIGIBLE = "Eligible"
VERDICT_WARNINGS = "Eligible with Warnings"
VERDICT_REVIEW = "Manual Review"
VERDICT_NOT_ELIGIBLE = "Not Eligible"
