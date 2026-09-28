TREE_DOCTYPE = "Custom LOS Loan Type Tree"
RULE_DOCTYPE = "Custom LOS Product Assignment Rule"
SETTINGS_DOCTYPE = "Custom LOS Product Assignment Settings"

# The DocType's tree parent field. The API calls it parent_node.
PARENT_FIELD = "parent_custom_los_loan_type_tree"

LEVEL_LOAN_TYPE = 1
LEVEL_SUB_TYPE = 2
LEVEL_PURPOSE = 3
LEVEL_LABELS = {LEVEL_LOAN_TYPE: "Loan Type", LEVEL_SUB_TYPE: "Sub-type", LEVEL_PURPOSE: "Purpose"}

APPLICANT_TYPES = ("Individual", "Business")

NODE_NAME_MAX_LENGTH = 140

ALLOWED_CREATE_FIELDS = {"node_name", "applicant_type", "parent_node", "is_active"}
ALLOWED_UPDATE_FIELDS = {"node_name", "is_active"}
SET_ONCE_FIELDS = {"applicant_type", "parent_node"}

ALLOWED_SORT_FIELDS = {"name", "node_name", "applicant_type", "level", "is_active", "creation", "modified"}

DEFAULT_SORT_BY = "level"
DEFAULT_SORT_ORDER = "asc"

SEARCH_FIELDS = ["name", "node_name"]

RETURN_FIELDS_GET_ALL = [
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
]

RETURN_FIELDS_GET_BY_ID = RETURN_FIELDS_GET_ALL + ["owner", "modified_by"]

# Smaller field set for the lookup endpoints (tree, loan types, sub-types, purposes).
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
