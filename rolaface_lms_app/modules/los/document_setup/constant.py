SETUP_DOCTYPE = "Custom LOS Product Document Setup"
LOAN_PRODUCT_DOCTYPE = "Loan Product"

ALLOWED_UPDATE_FIELDS = {"documents"}

ALLOWED_SORT_FIELDS = {"name", "loan_product", "product_name", "creation", "modified"}

DEFAULT_SORT_BY = "product_name"
DEFAULT_SORT_ORDER = "asc"

SEARCH_FIELDS = ["name", "product_name"]
PRODUCT_SEARCH_FIELDS = ["name", "product_name"]

RETURN_FIELDS_GET_ALL = ["name", "loan_product", "product_name", "documents", "creation", "modified"]

RETURN_FIELDS_GET_BY_ID = RETURN_FIELDS_GET_ALL + ["owner", "modified_by"]

DOCUMENT_NAME_MAX_LENGTH = 140
MAX_DOCUMENTS = 100
