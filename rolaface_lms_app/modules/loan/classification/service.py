import frappe
from frappe.utils import flt
from typing import Tuple, Dict, Any
from .utils import validate_classification_payload, validate_dpd_logic, get_target_company
from .constant import ALLOWED_SORT_FIELDS, PARENT_TYPE, DPD_RANGES_FIELD, PROVISION_RATES_FIELD

# ==========================================
# PUBLIC CRUD SERVICES
# ==========================================

def create_loan_classification(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_classification_payload(data, is_update=False)
    company = get_target_company(data)
    
    code = data.get("classificationCode")
    name = data.get("classificationName")
    min_dpd = flt(data.get("minDpdRange", 0))
    max_dpd = flt(data.get("maxDpdRange", 0))
    prov_rate = flt(data.get("provisionRate", 0.0))

    validate_dpd_logic(min_dpd, max_dpd)

    # 1. Ensure classification doesn't already exist globally
    if frappe.db.exists("Loan Classification", {"classification_code": code}):
        raise frappe.ValidationError(f"Loan Classification Code '{code}' already exists.")

    # 2. Insert Standalone Parent DocType
    cls_doc = frappe.new_doc("Loan Classification")
    cls_doc.classification_code = code
    cls_doc.classification_name = name
    cls_doc.insert(ignore_permissions=True)

    # 3. Explicitly Create & Attach DPD Child to Company
    dpd_child = frappe.new_doc("Loan Classification Range")
    dpd_child.parent = company
    dpd_child.parenttype = PARENT_TYPE
    dpd_child.parentfield = DPD_RANGES_FIELD
    dpd_child.classification_code = code
    dpd_child.classification_name = name
    dpd_child.min_dpd_range = min_dpd
    dpd_child.max_dpd_range = max_dpd
    dpd_child.insert(ignore_permissions=True)

    # 4. Explicitly Create & Attach Provisioning Child to Company
    prov_child = frappe.new_doc("Loan IRAC Provisioning Configuration")
    prov_child.parent = company
    prov_child.parenttype = PARENT_TYPE
    prov_child.parentfield = PROVISION_RATES_FIELD
    prov_child.classification_code = code
    prov_child.classification_name = name
    prov_child.provision_rate = prov_rate
    prov_child.insert(ignore_permissions=True)

    return get_loan_classification_by_id(code, company)


def update_loan_classification(code: str, data: Dict[str, Any]) -> Dict[str, Any]:
    validate_classification_payload(data, is_update=True)
    company = get_target_company(data)
    
    cls_name = frappe.db.get_value("Loan Classification", {"classification_code": code}, "name")
    if not cls_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{code}' not found.")

    new_name = data.get("classificationName")

    # 1. Update Standalone Parent
    if new_name:
        frappe.db.set_value("Loan Classification", cls_name, "classification_name", new_name)

    # 2. Update Company's DPD Range Child
    dpd_names = frappe.get_all("Loan Classification Range", filters={"parent": company, "classification_code": code}, pluck="name")
    if dpd_names:
        dpd_child = frappe.get_doc("Loan Classification Range", dpd_names[0])
        if new_name: dpd_child.classification_name = new_name
        if "minDpdRange" in data: dpd_child.min_dpd_range = flt(data["minDpdRange"])
        if "maxDpdRange" in data: dpd_child.max_dpd_range = flt(data["maxDpdRange"])
        validate_dpd_logic(dpd_child.min_dpd_range, dpd_child.max_dpd_range)
        dpd_child.save(ignore_permissions=True)

    # 3. Update Company's Provision Rate Child
    prov_names = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company, "classification_code": code}, pluck="name")
    if prov_names:
        prov_child = frappe.get_doc("Loan IRAC Provisioning Configuration", prov_names[0])
        if new_name: prov_child.classification_name = new_name
        if "provisionRate" in data: prov_child.provision_rate = flt(data["provisionRate"])
        prov_child.save(ignore_permissions=True)

    return get_loan_classification_by_id(code, company)


def get_loan_classification_by_id(code: str, company: str = None) -> Dict[str, Any]:
    company = company or get_target_company()

    cls_name = frappe.db.get_value("Loan Classification", {"classification_code": code}, "name")
    if not cls_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{code}' not found.")

    cls_doc = frappe.get_doc("Loan Classification", cls_name)

    # Fetch explicitly by company (parent)
    dpd_rows = frappe.get_all("Loan Classification Range", filters={"parent": company, "classification_code": code}, fields=["min_dpd_range", "max_dpd_range"])
    prov_rows = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company, "classification_code": code}, fields=["provision_rate"])

    return {
        "classificationCode": cls_doc.classification_code,
        "classificationName": cls_doc.classification_name,
        "minDpdRange": dpd_rows[0].min_dpd_range if dpd_rows else 0,
        "maxDpdRange": dpd_rows[0].max_dpd_range if dpd_rows else 0,
        "provisionRate": prov_rows[0].provision_rate if prov_rows else 0.0,
        "company": company
    }


def get_loan_classifications(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    company = get_target_company(args)
    start = (page - 1) * page_size
    or_filters = []

    if search := args.get("search"):
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["classification_code", "like", search_term],
            ["classification_name", "like", search_term]
        ]

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort field: {sort_by}")

    # Fetch Base Classifications
    classifications = frappe.get_all(
        "Loan Classification",
        or_filters=or_filters if search else None,
        fields=["classification_code", "classification_name"],
        limit_start=start,
        limit_page_length=page_size,
        order_by=f"`tabLoan Classification`.`{sort_by}` {sort_order}",
    )

    # Optimized O(1) Dictionary Mapping for Child Tables attached to the Company
    dpd_records = frappe.get_all("Loan Classification Range", filters={"parent": company}, fields=["classification_code", "min_dpd_range", "max_dpd_range"])
    prov_records = frappe.get_all("Loan IRAC Provisioning Configuration", filters={"parent": company}, fields=["classification_code", "provision_rate"])

    dpd_map = {r.classification_code: {"min": r.min_dpd_range, "max": r.max_dpd_range} for r in dpd_records}
    prov_map = {r.classification_code: r.provision_rate for r in prov_records}

    result = []
    for cls in classifications:
        code = cls.classification_code
        result.append({
            "classificationCode": code,
            "classificationName": cls.classification_name,
            "minDpdRange": dpd_map.get(code, {}).get("min", 0),
            "maxDpdRange": dpd_map.get(code, {}).get("max", 0),
            "provisionRate": prov_map.get(code, 0.0),
            "company": company
        })

    total_records = len(frappe.get_all(
        "Loan Classification",
        or_filters=or_filters if search else None,
        pluck="name"
    ))
    
    total_pages = (total_records + page_size - 1) // page_size

    return result, total_records, total_pages


def delete_loan_classification(code: str):
    cls_name = frappe.db.get_value("Loan Classification", {"classification_code": code}, "name")
    if not cls_name:
        raise frappe.DoesNotExistError(f"Loan Classification '{code}' not found.")


    frappe.db.delete("Loan Classification Range", {"classification_code": code})
    frappe.db.delete("Loan IRAC Provisioning Configuration", {"classification_code": code})
    
    # Finally, delete the standalone parent
    frappe.delete_doc("Loan Classification", cls_name, ignore_permissions=True)