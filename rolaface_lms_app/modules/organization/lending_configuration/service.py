import frappe
from typing import Dict, Any

from .utils import (
    validate_lending_config_payload, 
    flatten_config_payload, 
    nest_config_payload
)

DOCTYPE_NAME = "Custom Lending Configurations"

def _get_config_name_by_company(company: str) -> str:
    name = frappe.db.get_value(DOCTYPE_NAME, {"company": company}, "name")
    if not name:
        raise frappe.DoesNotExistError(f"Configuration for '{company}' does not exist.")
    return name

def create_lending_config(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not data.get("company"):
            data["company"] = frappe.defaults.get_user_default("Company")
            
        validate_lending_config_payload(data, is_update=False)

        company = data.get("company")
        if frappe.db.exists(DOCTYPE_NAME, {"company": company}):
            raise frappe.ValidationError(f"Configuration already exists for '{company}'.")

        flat_data = flatten_config_payload(data)
        config_doc = frappe.new_doc(DOCTYPE_NAME)

        for field, value in flat_data.items():
            config_doc.set(field, value)

        config_doc.insert(ignore_permissions=True)
        return get_lending_config(company)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        raise e

def update_lending_config(company: str, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        config_name = _get_config_name_by_company(company)
        config_doc = frappe.get_doc(DOCTYPE_NAME, config_name)

        if "company" in data and data["company"] != config_doc.company:
            raise frappe.ValidationError("Company cannot be changed.")

        validate_lending_config_payload(data, is_update=True)
        flat_data = flatten_config_payload(data)
        has_changes = False

        for field, value in flat_data.items():
            if config_doc.get(field) != value:
                config_doc.set(field, value)
                has_changes = True

        if has_changes:
            config_doc.save(ignore_permissions=True)

        return get_lending_config(company)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        raise e

def get_lending_config(company: str) -> Dict[str, Any]:
    config_name = _get_config_name_by_company(company)
    doc = frappe.get_doc(DOCTYPE_NAME, config_name)
    return nest_config_payload(doc.as_dict())

def delete_lending_config(company: str):
    config_name = _get_config_name_by_company(company)
    docstatus = frappe.db.get_value(DOCTYPE_NAME, config_name, "docstatus")
    
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete submitted configuration for '{company}'.")

    frappe.delete_doc(DOCTYPE_NAME, config_name, ignore_permissions=True)