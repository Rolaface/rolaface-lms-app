ALLOWED_CHARGE_FIELDS = {
    "item_code", "item_name", "item_group",
    "disabled", "description"
}

ALLOWED_SORT_FIELDS = {
    "name", "item_code", "item_name", "creation", "modified"
}

RETURN_FIELDS_GET_ALL = [
    "name", "item_code", "item_name", "item_group", "disabled", "creation"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_CHARGE_FIELDS) + [
    "name", "creation", "modified", "docstatus"
]