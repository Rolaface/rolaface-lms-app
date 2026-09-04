FIELD_MAPPING = {
    "relationship_manager": "account_manager"
}

TABLE_MAPPING = {
    "basic_details": "custom_basic_details",
    "extended_details": "custom_extended_details",
    "next_of_kin": "custom_next_of_kin",
    "stakeholders": "custom_stakeholders",
    "documents": "custom_documents"
}

ALLOWED_CUSTOMER_FIELDS = {
    "naming_series",
    "customer_type",
    "customer_name",
    "gender",
    "customer_group",
    "territory",
    "image",
    "default_currency",
    "default_bank_account",
    "default_price_list",
    "mobile_no",
    "email_id",
    "first_name",
    "last_name",
    "tax_id",
    "tax_category",
    "tax_withholding_category",
    "tax_withholding_group",
    "payment_terms",
    "is_internal_customer",
    "represents_company",
    "loyalty_program",
    "loyalty_program_tier",
    "account_manager", 
    "default_sales_partner",
    "default_commission_rate",
    "so_required",
    "dn_required",
    "disabled",
    "is_frozen",
    "lead_name",
    "opportunity_name",
    "prospect_name",
    "market_segment",
    "industry",
    "website",
    "language",
    "customer_pos_id",
    "customer_details",
    "is_npa"
}

ALLOWED_SORT_FIELDS = {
    "name",
    "creation",
    "modified",
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "disabled",
    "is_frozen"
}

RETURN_FIELDS_GET_ALL = [
    "name",
    "customer_name",
    "customer_type",
    "customer_group",
    "territory",
    "email_id",
    "mobile_no",
    "account_manager",
    "disabled"
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_CUSTOMER_FIELDS) + [
    "name",
    "creation",
    "modified",
    "docstatus",
    "customer_primary_address",
    "primary_address",
    "customer_primary_contact"
]