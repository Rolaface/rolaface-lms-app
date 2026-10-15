RULESET_DOCTYPE = "Custom LOS Prescreening Ruleset"
RULESET_LABEL = "a pre-screening rule set"

COPY_TO_DRAFT_FIELDS = ["ruleset_name", "description", "groups"]
ALLOWED_UPDATE_FIELDS = {"ruleset_name", "description", "effective_from", "effective_to", "groups"}

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

LOGICS = ("ALL", "ANY")
SEVERITIES = {
	"Blocking": "Reject Application",
	"Warning": "Continue with Warning",
	"Review": "Send for Manual Review",
}
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
