APPLICATION_DOCTYPE = "Custom LOS Loan Application"
CHANNEL_DOCTYPE = "Custom LOS Channel"
CUSTOMER_DOCTYPE = "Customer"
LOAN_PRODUCT_DOCTYPE = "Loan Product"
ADDRESS_DOCTYPE = "Address"

DRAFT = "Draft"
INDIVIDUAL = "Individual"
BUSINESS = "Business"
EXISTING_CUSTOMER = "Existing"

COMMON_FIELDS = (
	"application_date",
	"company",
	"channel",
	"customer_type",
	"customer",
	"applicant_type",
	"loan_type",
	"loan_sub_type",
	"loan_purpose",
	"requested_amount",
	"tenure_months",
	"repayment_frequency",
	"first_name",
	"middle_name",
	"last_name",
	"nrc",
	"phone",
	"email",
	"gender",
	"marital_status",
	"date_of_birth",
	"nationality",
)
BUSINESS_FIELDS = (
	"position",
	"company_name",
	"registration_number",
	"tpin",
	"business_type",
	"established_date",
	"nature_of_business",
)
INDIVIDUAL_FIELDS = (
	"kin_name",
	"kin_phone",
	"kin_email",
	"kin_relationship",
	"employment_status",
	"employment_type",
	"employer_name",
	"designation",
	"experience_years",
)
DATE_FIELDS = {"application_date", "date_of_birth", "established_date"}
MAX_TEXT_LENGTH = 140

TABLE_FIELDS = {
	"directors": ("full_name", "nrc", "phone", "email"),
	"collaterals": ("collateral_type", "estimated_value", "ownership_date", "description"),
	"documents": ("document_name", "file"),
}
FINANCIAL_KEYS = ("income", "obligations", "expenses")

ADDRESS_FIELDS = ("address_type", "address_line1", "address_line2", "city", "state", "country", "pincode")
ADDRESS_TYPES = ("Current", "Permanent", "Office")
REQUIRED_ADDRESS_TYPE = {INDIVIDUAL: "Current", BUSINESS: "Office"}

ALLOWED_UPDATE_FIELDS = {
	*COMMON_FIELDS,
	*BUSINESS_FIELDS,
	*INDIVIDUAL_FIELDS,
	*TABLE_FIELDS,
	"financials",
	"addresses",
}

ALLOWED_SORT_FIELDS = {"name", "application_date", "requested_amount", "creation", "modified"}

DEFAULT_SORT_BY = "modified"
DEFAULT_SORT_ORDER = "desc"

SEARCH_FIELDS = ["name", "first_name", "last_name", "company_name", "nrc", "phone"]

FILTER_FIELDS = (
	"status",
	"stage",
	"applicant_type",
	"channel",
	"customer",
	"loan_product",
	"prescreening_status",
	"appraisal_status",
	"underwriting_status",
	"offer_status",
)

RETURN_FIELDS_GET_ALL = [
	"name",
	"application_date",
	"status",
	"stage",
	"applicant_type",
	"first_name",
	"middle_name",
	"last_name",
	"company_name",
	"nrc",
	"phone",
	"customer",
	"channel",
	"loan_type",
	"loan_product",
	"requested_amount",
	"tenure_months",
	"repayment_frequency",
	"prescreening_status",
	"credit_score",
	"monthly_obligations",
	"eligible_amount",
	"appraisal_status",
	"approved_amount",
	"approved_tenure_months",
	"interest_rate",
	"underwriting_status",
	"underwriting_decision",
	"final_amount",
	"offer_status",
	"contract_status",
	"signing_method",
	"creation",
	"modified",
]
