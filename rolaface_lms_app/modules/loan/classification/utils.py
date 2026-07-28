import frappe
from frappe.utils import flt
from typing import Dict, Any

def get_target_company(data: Dict[str, Any] = None) -> str:
    company = data.get("company") if data else None
    if not company:
        company = frappe.defaults.get_user_default("Company")
    if not company:
        raise frappe.ValidationError("Company is required. Provide it in the payload or set a Default Company in Frappe.")
    if not frappe.db.exists("Company", company):
        raise frappe.ValidationError(f"Company '{company}' does not exist.")
    return company

def validate_classification_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        if not data.get("classificationCode"):
            raise frappe.ValidationError("classificationCode is required.")
        if not data.get("classificationName"):
            raise frappe.ValidationError("classificationName is required.")
        if "level" not in data or data.get("level") in ["", None]:
            raise frappe.ValidationError("level is required.")

    for field in ["minDpdRange", "maxDpdRange", "provisionRate"]:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"{field} cannot be negative.")

def validate_dpd_logic(min_dpd: float, max_dpd: float):
    if flt(min_dpd) > flt(max_dpd):
        raise frappe.ValidationError(f"Invalid Range: Minimum DPD ({min_dpd}) cannot exceed Maximum DPD ({max_dpd}).")

def validate_level_uniqueness(level: Any, ignore_parent: str = None):
    filters = {"level": level}
    if ignore_parent:
        filters["parent"] = ("!=", ignore_parent)
        
    if frappe.db.exists("Custom Loan Classification Extended Details", filters):
        raise frappe.ValidationError(f"Level '{level}' is already assigned to another Loan Classification.")

def build_classification_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    parent_filters = {}
    if not args:
        return parent_filters

    field_map = {
        "classificationCode": "classification_code",
        "classificationName": "classification_name"
    }
    
    for api_key, db_field in field_map.items():
        val = args.get(api_key) or args.get(db_field)
        if val:
            if isinstance(val, list):
                parent_filters[db_field] = ["in", val]
            elif isinstance(val, str) and "," in val:
                parent_filters[db_field] = ["in", [v.strip() for v in val.split(",")]]
            else:
                parent_filters[db_field] = val

    valid_codes_sets = []
    company_name = args.get("company") or frappe.defaults.get_user_default("Company")

    level_val = args.get("level")
    if level_val:
        if isinstance(level_val, str) and "," in level_val:
            level_val = [v.strip() for v in level_val.split(",")]
        level_op = "in" if isinstance(level_val, list) else "="
        valid_parents = frappe.get_all("Custom Loan Classification Extended Details", filters={"level": [level_op, level_val]}, pluck="parent")
        valid_codes_sets.append(set(valid_parents))

    min_prov = args.get("minProvisionRate") or args.get("min_provision_rate")
    max_prov = args.get("maxProvisionRate") or args.get("max_provision_rate")
    if min_prov is not None or max_prov is not None:
        prov_filters = {}
        if company_name:
            prov_filters["parent"] = company_name

        if min_prov is not None and max_prov is not None:
            prov_filters["provision_rate"] = ["between", [flt(min_prov), flt(max_prov)]]
        elif min_prov is not None:
            prov_filters["provision_rate"] = [">=", flt(min_prov)]
        elif max_prov is not None:
            prov_filters["provision_rate"] = ["<=", flt(max_prov)]
        
        valid_prov_codes = frappe.get_all("Loan IRAC Provisioning Configuration", filters=prov_filters, pluck="classification_code")
        valid_codes_sets.append(set(valid_prov_codes))

    min_dpd = args.get("minDpdRange") or args.get("min_dpd_range")
    max_dpd = args.get("maxDpdRange") or args.get("max_dpd_range")
    if min_dpd is not None or max_dpd is not None:
        dpd_filters = {}
        if company_name:
            dpd_filters["parent"] = company_name

        if min_dpd is not None:
            dpd_filters["min_dpd_range"] = [">=", flt(min_dpd)]
        if max_dpd is not None:
            dpd_filters["max_dpd_range"] = ["<=", flt(max_dpd)]
            
        valid_dpd_codes = frappe.get_all("Loan Classification Range", filters=dpd_filters, pluck="classification_code")
        valid_codes_sets.append(set(valid_dpd_codes))

    if valid_codes_sets:
        intersected_codes = set.intersection(*valid_codes_sets)
        if not intersected_codes:
            parent_filters["classification_code"] = ["in", ["__EMPTY_SET__"]]
        else:
            if "classification_code" in parent_filters:
                existing = parent_filters["classification_code"]
                existing_list = set(existing[1]) if isinstance(existing, list) and existing[0] == "in" else {existing}
                final_codes = list(existing_list.intersection(intersected_codes))
                parent_filters["classification_code"] = ["in", final_codes if final_codes else ["__EMPTY_SET__"]]
            else:
                parent_filters["classification_code"] = ["in", list(intersected_codes)]

    return parent_filters