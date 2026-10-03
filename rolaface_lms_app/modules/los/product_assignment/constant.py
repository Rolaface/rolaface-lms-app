SETTINGS_DOCTYPE = "Custom LOS Product Assignment Settings"
RULE_DOCTYPE = "Custom LOS Product Assignment Rule"
CHANNEL_DOCTYPE = "Custom LOS Channel"
TREE_DOCTYPE = "Custom LOS Loan Type Tree"
LOAN_PRODUCT_DOCTYPE = "Loan Product"

LEVEL_LOAN_TYPE = 1
LEVEL_PURPOSE = 3


MATCH_FIRST = "First match"
MATCH_MANUAL_REVIEW = "Manual Review"
SEVERAL_MATCH_OPTIONS = (MATCH_FIRST, MATCH_MANUAL_REVIEW)

NO_MATCH_MANUAL_REVIEW = "Manual Review"
NO_MATCH_DEFAULT_PRODUCT = "Default Product"
NO_MATCH_OPTIONS = (NO_MATCH_MANUAL_REVIEW, NO_MATCH_DEFAULT_PRODUCT)

SETTINGS_FIELDS = ("several_match", "no_match", "default_product")


ALLOWED_UPDATE_FIELDS = {"sources", "loan_types", "condition"}

ALLOWED_SORT_FIELDS = {"name", "product_name", "is_active", "creation", "modified"}

DEFAULT_SORT_BY = "product_name"
DEFAULT_SORT_ORDER = "asc"

SEARCH_FIELDS = ["name", "product_name"]

RETURN_FIELDS_GET_ALL = [
	"name",
	"product",
	"product_name",
	"sources",
	"loan_types",
	"condition",
	"is_active",
	"creation",
	"modified",
]
RETURN_FIELDS_GET_BY_ID = RETURN_FIELDS_GET_ALL + ["owner", "modified_by"]


JOINERS = ("AND", "OR")
NUMBER_OPERATORS = ("=", "<>", ">", ">=", "<", "<=")
LIST_OPERATORS = ("=", "<>")

VARIABLES = {
	"customer_type": {"label": "Customer type", "numeric": False, "options": ("New to bank", "Existing customer", "Staff")},
	"employment_type": {
		"label": "Employment type",
		"numeric": False,
		"options": ("Salaried", "Self-employed", "Business owner", "Pensioner"),
	},
	"vehicle_condition": {"label": "Vehicle condition", "numeric": False, "options": ("New", "Used")},
	"credit_score": {"label": "Credit score", "numeric": True},
	"net_monthly_income": {"label": "Net monthly income", "numeric": True},
	"loan_amount": {"label": "Loan amount", "numeric": True},
	"tenor": {"label": "Tenor (months)", "numeric": True},
	"age": {"label": "Age", "numeric": True},
	"years_in_business": {"label": "Years in business", "numeric": True},
}


STATUS_RULE_MATCHED = "Rule matched"
STATUS_LOAN_TYPE_DEFAULT = "Loan type default"
STATUS_MANUAL_REVIEW = "Manual review"
STATUS_CONFLICT = "Conflict"
