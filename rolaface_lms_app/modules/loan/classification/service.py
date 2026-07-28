import frappe
from frappe.utils import flt
from typing import Tuple, Dict, Any
from .utils import validate_classification_payload, validate_dpd_logic, validate_level_uniqueness, get_target_company, build_classification_filters
from .constant import ALLOWED_SORT_FIELDS

def create_loan_classification(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_classification_payload(data, is_update=False)
    company_name = get_target_company(data)
    
    classification_code = data.get("classificationCode")
    classification_name = data.get("classificationName")
    classification_level = data.get("level")
    min_dpd_range = flt(data.get("minDpdRange", 0))
    max_dpd_range = flt(data.get("maxDpdRange", 0))
    provision_rate = flt(data.get("provisionRate", 0.0))

    validate_dpd_logic(min_dpd_range, max_dpd_range)
    validate_level_uniqueness(classification_level)

    if frappe.db.exists("Loan Classification", {"classification_code": classification_code}):
        raise frappe.ValidationError(f"Loan Classification Code '{classification_code}' already exists.")

    loan_classification_doc = frappe.new_doc("Loan Classification")
    loan_classification_doc.classification_code = classification_code
    loan_classification_doc.classification_name = classification_name
    loan_classification_doc.insert(ignore_permissions=True)
    
    loan_classification_name = loan_classification_doc.name

    extended_details_doc = frappe.new_doc("Custom Loan Classification Extended Details")
    extended_details_doc.parent = loan_classification_name
    extended_details_doc.parenttype = "Loan Classification"
    extended_details_doc.parentfield = "custom_loan_classification_extended_details"
    extended_details_doc.level = classification_level
    extended_details_doc.insert(ignore_permissions=True)

    dpd_range_doc = frappe.new_doc("Loan Classification Range")
    dpd_range_doc.parent = company_name
    dpd_range_doc.parenttype = "Company"
    dpd_range_doc.parentfield = "loan_classification_ranges"
    dpd_range_doc.classification_code = classification_code
    dpd_range_doc.classification_name = classification_name
    dpd_range_doc.min_dpd_range = min_dpd_range
    dpd_range_doc.max_dpd_range = max_dpd_range
    dpd_range_doc.insert(ignore_permissions=True)

    provision_rate_doc = frappe.new_doc("Loan IRAC Provisioning Configuration")
    provision_rate_doc.parent = company_name
    provision_rate_doc.parenttype = "Company"
    provision_rate_doc.parentfield = "irac_provisioning_configurations"
    provision_rate_doc.classification_code = classification_code
    provision_rate_doc.classification_name = classification_name
    provision_rate_doc.provision_rate = provision_rate
    provision_rate_doc.insert(ignore_permissions=True)

    return get_loan_classification_by_id(classification_code, company_name)


def update_loan_classification(classification_code: str, data: Dict[str, Any]) -> Dict[str, Any]:
    validate_classification_payload(data, is_update=True)
    company_name = get_target_company(data)
    
    loan_classification_name = frappe.db.get_value("Loan Classification", {"classification_code": classification_code}, "name")
    if not loan_classification_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{classification_code}' not found.")

    new_classification_name = data.get("classificationName")

    if new_classification_name:
        frappe.db.set_value("Loan Classification", loan_classification_name, "classification_name", new_classification_name)

    if "level" in data:
        validate_level_uniqueness(data["level"], ignore_parent=loan_classification_name)
        extended_details_names = frappe.get_all("Custom Loan Classification Extended Details", filters={"parent": loan_classification_name}, pluck="name")
        
        if extended_details_names:
            extended_details_doc = frappe.get_doc("Custom Loan Classification Extended Details", extended_details_names[0])
            extended_details_doc.level = data["level"]
            extended_details_doc.save(ignore_permissions=True)
        else:
            extended_details_doc = frappe.new_doc("Custom Loan Classification Extended Details")
            extended_details_doc.parent = loan_classification_name
            extended_details_doc.parenttype = "Loan Classification"
            extended_details_doc.parentfield = "custom_loan_classification_extended_details"
            extended_details_doc.level = data["level"]
            extended_details_doc.insert(ignore_permissions=True)

    dpd_range_names = frappe.get_all("Loan Classification Range", filters={"parent": company_name, "classification_code": classification_code}, pluck="name")
    if dpd_range_names:
        dpd_range_doc = frappe.get_doc("Loan Classification Range", dpd_range_names[0])
        if new_classification_name: 
            dpd_range_doc.classification_name = new_classification_name
        if "minDpdRange" in data: 
            dpd_range_doc.min_dpd_range = flt(data["minDpdRange"])
        if "maxDpdRange" in data: 
            dpd_range_doc.max_dpd_range = flt(data["maxDpdRange"])
        validate_dpd_logic(dpd_range_doc.min_dpd_range, dpd_range_doc.max_dpd_range)
        dpd_range_doc.save(ignore_permissions=True)

    provision_rate_names = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company_name, "classification_code": classification_code}, pluck="name")
    if provision_rate_names:
        provision_rate_doc = frappe.get_doc("Loan IRAC Provisioning Configuration", provision_rate_names[0])
        if new_classification_name: 
            provision_rate_doc.classification_name = new_classification_name
        if "provisionRate" in data: 
            provision_rate_doc.provision_rate = flt(data["provisionRate"])
        provision_rate_doc.save(ignore_permissions=True)

    return get_loan_classification_by_id(classification_code, company_name)


def get_loan_classification_by_id(classification_code: str, company_name: str = None) -> Dict[str, Any]:
    company_name = company_name or get_target_company()

    loan_classification_name = frappe.db.get_value("Loan Classification", {"classification_code": classification_code}, "name")
    if not loan_classification_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{classification_code}' not found.")

    loan_classification_doc = frappe.get_doc("Loan Classification", loan_classification_name)
    
    extended_details_records = frappe.get_all("Custom Loan Classification Extended Details", filters={"parent": loan_classification_name}, fields=["level"])
    dpd_range_records = frappe.get_all("Loan Classification Range", filters={"parent": company_name, "classification_code": classification_code}, fields=["min_dpd_range", "max_dpd_range"])
    provision_rate_records = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company_name, "classification_code": classification_code}, fields=["provision_rate"])

    return {
        "classificationCode": loan_classification_doc.classification_code,
        "classificationName": loan_classification_doc.classification_name,
        "level": extended_details_records[0].level if extended_details_records else None,
        "minDpdRange": dpd_range_records[0].min_dpd_range if dpd_range_records else 0,
        "maxDpdRange": dpd_range_records[0].max_dpd_range if dpd_range_records else 0,
        "provisionRate": provision_rate_records[0].provision_rate if provision_rate_records else 0.0,
        "company": company_name
    }


def get_loan_classifications(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    company_name = get_target_company(args)
    start_index = (page - 1) * page_size
    query_or_filters = []

    search_term = args.get("search")
    if search_term:
        formatted_search_term = f"%{str(search_term).strip()}%"
        query_or_filters = [
            ["classification_code", "like", formatted_search_term],
            ["classification_name", "like", formatted_search_term]
        ]

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort field: {sort_by}")

    safe_filters = build_classification_filters(args)

    loan_classifications = frappe.get_all(
        "Loan Classification",
        filters=safe_filters,
        or_filters=query_or_filters if search_term else None,
        fields=["name", "classification_code", "classification_name", "creation", "modified"]
    )

    level_records = frappe.get_all("Custom Loan Classification Extended Details", fields=["parent", "level"])
    level_map = {record.parent: record.level for record in level_records}

    dpd_range_records = frappe.get_all("Loan Classification Range", filters={"parent": company_name}, fields=["classification_code", "min_dpd_range", "max_dpd_range"])
    provision_rate_records = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company_name}, fields=["classification_code", "provision_rate"])

    dpd_range_map = {record.classification_code: {"min": record.min_dpd_range, "max": record.max_dpd_range} for record in dpd_range_records}
    provision_rate_map = {record.classification_code: record.provision_rate for record in provision_rate_records}

    full_results = []
    for classification_record in loan_classifications:
        current_code = classification_record.classification_code
        full_results.append({
            "classificationCode": current_code,
            "classificationName": classification_record.classification_name,
            "level": level_map.get(classification_record.name),
            "minDpdRange": dpd_range_map.get(current_code, {}).get("min", 0),
            "maxDpdRange": dpd_range_map.get(current_code, {}).get("max", 0),
            "provisionRate": provision_rate_map.get(current_code, 0.0),
            "company": company_name,
            "creation": classification_record.creation,
            "modified": classification_record.modified
        })

    sort_field_map = {
        "level": "level",
        "provisionRate": "provisionRate",
        "provision_rate": "provisionRate",
        "minDpdRange": "minDpdRange",
        "min_dpd_range": "minDpdRange",
        "maxDpdRange": "maxDpdRange",
        "max_dpd_range": "maxDpdRange",
        "classificationCode": "classificationCode",
        "classification_code": "classificationCode",
        "name": "classificationCode",
        "classificationName": "classificationName",
        "classification_name": "classificationName",
        "creation": "creation",
        "modified": "modified"
    }

    mapped_sort_by = sort_field_map.get(sort_by, "creation")
    is_reverse = (str(sort_order).lower() == "desc")

    def sort_key(item):
        val = item.get(mapped_sort_by)
        if val is None:
            return "" if mapped_sort_by in ["level", "classificationCode", "classificationName"] else 0
        return str(val) if mapped_sort_by in ["creation", "modified"] else val

    full_results.sort(key=sort_key, reverse=is_reverse)

    total_records = len(full_results)
    total_pages = (total_records + page_size - 1) // page_size
    paginated_results = full_results[start_index:start_index + page_size]

    for result in paginated_results:
        result.pop("creation", None)
        result.pop("modified", None)

    return paginated_results, total_records, total_pages


def delete_loan_classification(classification_code: str):
    loan_classification_name = frappe.db.get_value("Loan Classification", {"classification_code": classification_code}, "name")
    if not loan_classification_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{classification_code}' not found.")

    frappe.db.delete("Loan Classification Range", {"classification_code": classification_code})
    frappe.db.delete("Loan IRAC Provisioning Configuration", {"classification_code": classification_code})
    frappe.db.delete("Custom Loan Classification Extended Details", {"parent": loan_classification_name})
    
    frappe.delete_doc("Loan Classification", loan_classification_name, ignore_permissions=True)