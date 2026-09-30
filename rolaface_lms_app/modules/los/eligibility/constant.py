RULE_DOCTYPE = "Custom LOS Eligibility Rule"
RULE_LABEL = "an eligibility rule"
RULE_NAME_MAX_LENGTH = 140

SECTIONS = {
	"income_sources": list,
	"obligation_sources": list,
	"credit_bands": list,
	"internal_bands": list,
	"collateral_items": list,
	"formula_params": dict,
	"hard_stops": list,
	"manual_reviews": list,
}

FREE_FORM_SECTIONS = {"hard_stops", "manual_reviews"}

COLLATERAL_KEYS = ("type", "haircut_pct", "max_ltv_pct")

FORMULA_KEYS = (
	"other_income_recognition",
	"salary_multiple",
	"max_emi_ratio",
	"max_dti_ratio",
	"affordability_buffer",
	"product_max",
)

ALLOWED_UPDATE_FIELDS = {"rule_name", "effective_from", "effective_to", *SECTIONS}
COPY_TO_DRAFT_FIELDS = ["rule_name", *SECTIONS]

LIST_FIELDS = ["name", "rule_name", "loan_product", "version", "status", "effective_from", "effective_to", "modified", "modified_by"]
RETURN_FIELDS = [*LIST_FIELDS, *SECTIONS, "owner", "creation"]
