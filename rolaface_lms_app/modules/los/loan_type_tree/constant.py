TREE_DOCTYPE = "Custom LOS Loan Type Tree"
RULE_DOCTYPE = "Custom LOS Product Assignment Rule"
SETTINGS_DOCTYPE = "Custom LOS Product Assignment Settings"

PARENT_FIELD = "parent_custom_los_loan_type_tree"

LEVEL_LOAN_TYPE = 1
LEVEL_SUB_TYPE = 2
LEVEL_PURPOSE = 3
LEVEL_LABELS = {LEVEL_LOAN_TYPE: "Loan Type", LEVEL_SUB_TYPE: "Sub-type", LEVEL_PURPOSE: "Purpose"}

APPLICANT_TYPES = ("Individual", "Business")

NODE_NAME_MAX_LENGTH = 140

ALLOWED_UPDATE_FIELDS = {"node_name"}
SET_ONCE_FIELDS = {"applicant_type", "parent_node"}

RETURN_FIELDS_GET_BY_ID = [
	"name",
	"node_name",
	"applicant_type",
	"level",
	f"{PARENT_FIELD} as parent_node",
	"loan_type",
	"sub_type",
	"is_group",
	"is_active",
	"creation",
	"modified",
	"owner",
	"modified_by",
]

RETURN_FIELDS_LOOKUP = [
	"name",
	"node_name",
	"applicant_type",
	"level",
	f"{PARENT_FIELD} as parent_node",
	"loan_type",
	"sub_type",
	"is_active",
]
