import frappe
from typing import Dict, Any
from .constant import ROOT_FIELDS, ACCOUNT_CATEGORIES

def validate_lending_config_payload(data: Dict[str, Any], is_update: bool = False):
    company = data.get("company")

    if not is_update and not company:
        raise frappe.ValidationError("Company is required.")

    if company and not frappe.db.exists("Company", company):
        raise frappe.ValidationError(f"Company '{company}' does not exist.")

    default_accounts = data.get("default_accounts", {})
    if default_accounts and not isinstance(default_accounts, dict):
        raise frappe.ValidationError("'default_accounts' must be a JSON object.")

    for category, fields in ACCOUNT_CATEGORIES.items():
        category_data = default_accounts.get(category, {})
        if not isinstance(category_data, dict):
            continue
            
        for field in fields:
            if field == "same_as_interest":
                continue
            
            account_name = category_data.get(field)
            if account_name:
                check_company = company or frappe.db.get_value("Account", account_name, "company")
                if not frappe.db.exists("Account", {"name": account_name, "company": check_company}):
                    raise frappe.ValidationError(
                        f"Account '{account_name}' provided for '{field}' does not exist in company '{check_company}'."
                    )

def flatten_config_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    flat_data = {}
    
    for field in ROOT_FIELDS:
        if field in data and data.get(field) is not None:
            flat_data[field] = data[field]
            
    default_accounts = data.get("default_accounts", {})
    for category, fields in ACCOUNT_CATEGORIES.items():
        category_data = default_accounts.get(category, {})
        for field in fields:
            if field in category_data and category_data.get(field) is not None:
                flat_data[field] = category_data[field]
                
    return flat_data

def nest_config_payload(doc_dict: Dict[str, Any]) -> Dict[str, Any]:
    nested_data = {"default_accounts": {}}
    
    for field in ROOT_FIELDS:
        if field in doc_dict:
            nested_data[field] = doc_dict[field]
            
    for category, fields in ACCOUNT_CATEGORIES.items():
        nested_data["default_accounts"][category] = {}
        for field in fields:
            if field in doc_dict:
                nested_data["default_accounts"][category][field] = doc_dict[field]
                
    return nested_data