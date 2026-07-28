ALLOWED_CLASSIFICATION_PAYLOAD = {
    "classificationCode", "classificationName", 
    "minDpdRange", "maxDpdRange", "provisionRate", "company"
}

ALLOWED_SORT_FIELDS = {
    "name", "classification_name", "classification_code", "creation", "modified"
}

PARENT_TYPE = "Company"
DPD_RANGES_FIELD = "loan_classification_ranges"  
PROVISION_RATES_FIELD = "irac_provisioning_configuration"