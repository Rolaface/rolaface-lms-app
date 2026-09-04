import frappe
from typing import Tuple, Dict, Any

from .utils import (
    validate_customer_payload, 
    sync_addresses, 
    sync_contacts,
    get_linked_addresses,
    get_linked_contacts,
    build_customer_filters,
    transform_payload_to_db,
    transform_db_to_payload
)
from .constant import (
    ALLOWED_CUSTOMER_FIELDS,
    TABLE_MAPPING,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
)

def create_customer(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        db_payload = transform_payload_to_db(data)
        validate_customer_payload(db_payload, is_update=False)

        customer = frappe.new_doc("Customer")
        
        for field in ALLOWED_CUSTOMER_FIELDS:
            if field in db_payload and db_payload.get(field) is not None:
                customer.set(field, db_payload.get(field))
                
        for db_table_name in TABLE_MAPPING.values():
            if db_table_name in db_payload and isinstance(db_payload.get(db_table_name), list):
                customer.set(db_table_name, db_payload.get(db_table_name))
        
        customer.insert(ignore_permissions=True)

        if data.get("addresses"):
            sync_addresses(customer, data.get("addresses"), is_update=False)
        if data.get("contacts"):
            sync_contacts(customer, data.get("contacts"), is_update=False)

        return get_customer_by_id(customer.name)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            db.rollback()
        raise e


def update_customer(customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not frappe.db.exists("Customer", customer_id):
            raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

        db_payload = transform_payload_to_db(data)
        db_payload["name"] = customer_id
        validate_customer_payload(db_payload, is_update=True)
        
        customer = frappe.get_doc("Customer", customer_id)
        has_changes = False

        for field in ALLOWED_CUSTOMER_FIELDS:
            if field in db_payload and db_payload.get(field) is not None:
                if customer.get(field) != db_payload.get(field):
                    customer.set(field, db_payload.get(field))
                    has_changes = True

        for db_table_name in TABLE_MAPPING.values():
            if db_table_name in db_payload and isinstance(db_payload.get(db_table_name), list):
                customer.set(db_table_name, db_payload.get(db_table_name))
                has_changes = True

        if has_changes:
            customer.save(ignore_permissions=True)

        if "addresses" in data:
            sync_addresses(customer, data.get("addresses"), is_update=True)
        if "contacts" in data:
            sync_contacts(customer, data.get("contacts"), is_update=True)

        return get_customer_by_id(customer.name)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            db.rollback()
        raise e


def get_customer_by_id(customer_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    doc = frappe.get_doc("Customer", customer_id)
    raw_result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    for db_table_name in TABLE_MAPPING.values():
        raw_result[db_table_name] = [row.as_dict() for row in doc.get(db_table_name, [])]

    raw_result["status"] = "active" if not doc.disabled else "inactive"
    raw_result["addresses"] = get_linked_addresses("Customer", customer_id)
    raw_result["contacts"] = get_linked_contacts("Customer", customer_id)

    return transform_db_to_payload(raw_result)


def get_customers(
    args: Dict[str, Any],
    page: int,
    page_size: int,
    sort_by="creation",
    sort_order="desc",
) -> Tuple[list, int, int]:
    
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["customer_name", "like", search_term],
            ["email_id", "like", search_term],
            ["mobile_no", "like", search_term],
            ["tax_id", "like", search_term]
        ]

    filters = build_customer_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabCustomer`.`{sort_by}` {sort_order_clean}"

    customers = frappe.get_all(
        "Customer",
        filters=filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_customers = len(frappe.get_all(
        "Customer", 
        filters=filters, 
        or_filters=or_filters if search else None, 
        pluck="name"
    ))
    
    total_pages = (total_customers + page_size - 1) // page_size

    clean_customers = []
    for c in customers:
        if "disabled" in c:
            c["status"] = "inactive" if c.pop("disabled") else "active"
        clean_customers.append(transform_db_to_payload(c))

    return clean_customers, total_customers, total_pages


def delete_customer(customer_id: str):
    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    frappe.db.set_value("Customer", customer_id, {
        "customer_primary_contact": None,
        "customer_primary_address": None,
    }, update_modified=False)

    frappe.delete_doc("Customer", customer_id, ignore_permissions=True)


def update_customer_status(customer_id: str, action: str):
    if action not in ["active", "inactive"]:
        raise frappe.ValidationError("Action must be 'active' or 'inactive'.")

    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    is_disabled = 1 if action == "inactive" else 0
    frappe.db.set_value("Customer", customer_id, "disabled", is_disabled)
    
    return {"id": customer_id, "status": action}