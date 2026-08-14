ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS = {
    # Application Details
    "application_type",
    "customer",
    "application_date",
    "status",
    "amount",
    "tenure",
    "total_amount",
    # Personal Loan - Personal Information
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "email",
    "national_registration_card",
    "gender",
    "marital_status",
    "birth_date",
    # Personal Loan - Residence & Employment
    "residential_address",
    "occupation",
    "employer_name",
    "nationality",
    "loan_purpose",
    "next_of_kin_name",
    "next_of_kin_phone",
    "next_of_kin_email",
    "next_of_kin_relationship",
    # Business Loan - Business Information
    "company_name",
    "type_of_business",
    "established_date",
    "nature_of_business",
    "registered_office",
    "collateral_pledged",
    "purpose_of_loan",
    # Business Loan - Applicant Information
    "applicant_first_name",
    "applicant_middle_name",
    "applicant_last_name",
    "applicant_phone",
    "applicant_email",
    "applicant_national_registration_card",
    "applicant_gender",
    "applicant_marital_status",
    "applicant_birth_date",
    "applicant_address",
    "applicant_position",
    "applicant_nationality",
}

RETURN_FIELDS_GET_ALL = [
    "name",
    "application_type",
    "customer",
    "status",
    "application_date",
    "amount",
    "total_amount",
]

RETURN_FIELDS_GET_BY_ID = list(ALLOWED_CUSTOM_LOAN_APPLICATION_FIELDS) + [
    "name",
    "creation",
    "modified",
    "docstatus",
    "naming_series",
]

ALLOWED_SORT_FIELDS = {
    "name",
    "creation",
    "modified",
    "application_date",
    "application_type",
    "status",
    "customer",
    "amount",
    "total_amount",
}

RETURN_FIELDS_GET_ALL = [
    "name",
    "application_type",
    "customer",
    "status",
    "application_date",
    "first_name",
    "last_name",
    "company_name",
    "amount",
    "total_amount",
]

CONVERTIBLE_STATUS = "Submitted"
CUSTOMER_GROUP = "All Customer Groups"
TERRITORY = "All Territories"
