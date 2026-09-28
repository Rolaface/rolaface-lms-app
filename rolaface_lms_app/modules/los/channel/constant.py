CHANNEL_DOCTYPE = "Custom LOS Channel"
RULE_DOCTYPE = "Custom LOS Product Assignment Rule"

ALLOWED_CHANNEL_FIELDS = {"channel_name", "is_active"}

ALLOWED_SORT_FIELDS = {"name", "channel_name", "is_active", "creation", "modified"}

DEFAULT_SORT_BY = "channel_name"
DEFAULT_SORT_ORDER = "asc"

SEARCH_FIELDS = ["name", "channel_name"]

RETURN_FIELDS_GET_ALL = ["name", "channel_name", "is_active", "creation", "modified"]

RETURN_FIELDS_GET_BY_ID = RETURN_FIELDS_GET_ALL + ["owner", "modified_by"]

CHANNEL_NAME_MAX_LENGTH = 140
