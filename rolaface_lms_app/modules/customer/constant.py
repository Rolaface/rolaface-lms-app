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

CHILD_ROW_NAME_FIELD = {"name"}

BASIC_DETAILS_FIELDS = CHILD_ROW_NAME_FIELD | {
    "national_identification_number",
    "date_of_birth",
    "gender",
    "marital_status",
    "nationality",
    "is_staff_customer",
    "staff_id",
    "occupation",
    "registered_company_name",
    "registration_number",
    "incorporation_date",
    "education_level",
    "employment_type",
    "industry_type",
    "employer_name",
    "source_of_income",
    "monthly_income",
    "annual_income",
    "total_assets",
    "total_liabilities",
    "net_worth",
    "existing_monthly_obligations",
    "annual_revenue",
    "number_of_employees"
}

EXTENDED_DETAILS_FIELDS = CHILD_ROW_NAME_FIELD | {
    "registration_no",
    "strict_credit_limit",
    "principal_id"
}

NEXT_OF_KIN_FIELDS = CHILD_ROW_NAME_FIELD | {
    "first_name",
    "middle_name",
    "last_name",
    "relationship",
    "phone",
    "address_line_1",
    "address_line_2",
    "city",
    "district",
    "state",
    "country",
    "postal_code"
}

STAKEHOLDER_FIELDS = CHILD_ROW_NAME_FIELD | {
    "stakeholder_name",
    "stakeholder_role",
    "ownership_percentage"
}

DOCUMENT_FIELDS = CHILD_ROW_NAME_FIELD | {
    "document_type",
    "document_name",
    "document_number",
    "issue_date",
    "expiry_date",
    "verification_status",
    "issuing_authority",
    "place_of_issue",
    "document_upload",
    "issuing_country"
}

CHILD_TABLE_FIELDS = {
    "basic_details": BASIC_DETAILS_FIELDS,
    "extended_details": EXTENDED_DETAILS_FIELDS,
    "next_of_kin": NEXT_OF_KIN_FIELDS,
    "stakeholders": STAKEHOLDER_FIELDS,
    "documents": DOCUMENT_FIELDS
}

ADDRESS_FIELDS = {
    "name",
    "address_type",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "pincode",
    "country",
    "is_primary_address",
    "is_shipping_address"
}

CONTACT_FIELDS = {
    "name",
    "first_name",
    "last_name",
    "salutation",
    "designation",
    "email_id",
    "mobile_no",
    "is_primary_contact",
    "is_billing_contact"
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
