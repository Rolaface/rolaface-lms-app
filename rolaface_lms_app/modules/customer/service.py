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
    ADDRESS_FIELDS,
    CHILD_TABLE_FIELDS,
    CONTACT_FIELDS,
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
        
        customer.insert()

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
            if field in db_payload:
                if customer.get(field) != db_payload.get(field):
                    customer.set(field, db_payload.get(field))
                    has_changes = True

        for db_table_name in TABLE_MAPPING.values():
            if db_table_name in db_payload and isinstance(db_payload.get(db_table_name), list):
                customer.set(db_table_name, db_payload.get(db_table_name))
                has_changes = True

        if has_changes:
            customer.save()

        if "addresses" in data:
            sync_addresses(customer, data.get("addresses"), is_update=True)
        if "contacts" in data:
            sync_contacts(customer, data.get("contacts"), is_update=True)

        return get_customer_by_id(customer.name)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            db.rollback()
        raise e


def _get_customer_account_map(customer_names: list) -> Dict[str, Any]:
    """Customer -> receivable Account set in the customer's Accounts table for the default Company."""
    company = frappe.defaults.get_user_default("Company")
    if not customer_names or not company:
        return {}

    rows = frappe.get_all(
        "Party Account",
        filters={
            "parent": ["in", customer_names],
            "parenttype": "Customer",
            "company": company,
        },
        fields=["parent", "account"],
    )
    return {r["parent"]: r["account"] for r in rows}


def get_customer_by_id(customer_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    doc = frappe.get_doc("Customer", customer_id)
    doc.check_permission("read")
    raw_result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    for api_table_name, db_table_name in TABLE_MAPPING.items():
        allowed_fields = CHILD_TABLE_FIELDS.get(api_table_name, set())
        raw_result[db_table_name] = [
            {field: value for field, value in row.as_dict().items() if field in allowed_fields}
            # for row in doc.get(db_table_name, [])
            for row in (doc.get(db_table_name) or [])
        ]

    raw_result["status"] = "active" if not doc.disabled else "inactive"
    raw_result["account"] = _get_customer_account_map([customer_id]).get(customer_id)
    raw_result["addresses"] = [
        {field: value for field, value in address.items() if field in ADDRESS_FIELDS}
        for address in get_linked_addresses("Customer", customer_id)
    ]
    raw_result["contacts"] = [
        {field: value for field, value in contact.items() if field in CONTACT_FIELDS}
        for contact in get_linked_contacts("Customer", customer_id)
    ]

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

    count_result = frappe.get_all(
        "Customer", 
        filters=filters, 
        or_filters=or_filters if search else None,
        fields=[{"COUNT": "*", "as": "count"}],
    )
    total_customers = int(count_result[0].get("count") or 0) if count_result else 0
    
    total_pages = (total_customers + page_size - 1) // page_size
    customer_names = [c["name"] for c in customers]
    investor_map = {}

    if customer_names:
        rows = frappe.get_all(
            "Custom Lending Customer Extended Details",
            filters={
                "parent": ["in", customer_names],
                "parenttype": "Customer",
                "parentfield": TABLE_MAPPING["basic_details"],
            },
            fields=["parent", "is_investor"],
        )
        for r in rows:
            investor_map[r["parent"]] = investor_map.get(r["parent"], 0) or r["is_investor"]

    account_map = _get_customer_account_map(customer_names)

    clean_customers = []
    for c in customers:
        if "disabled" in c:
            c["status"] = "inactive" if c.pop("disabled") else "active"
        c["is_investor"] = bool(investor_map.get(c["name"], 0)) 
        c["account"] = account_map.get(c["name"])
        clean_customers.append(transform_db_to_payload(c))

    return clean_customers, total_customers, total_pages


def delete_customer(customer_id: str):
    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    frappe.db.set_value("Customer", customer_id, {
        "customer_primary_contact": None,
        "customer_primary_address": None,
    }, update_modified=False)

    frappe.delete_doc("Customer", customer_id)


def update_customer_status(customer_id: str, action: str):
    if action not in ["active", "inactive"]:
        raise frappe.ValidationError("Action must be 'active' or 'inactive'.")

    if not frappe.db.exists("Customer", customer_id):
        raise frappe.DoesNotExistError(f"Customer '{customer_id}' does not exist.")

    is_disabled = 1 if action == "inactive" else 0
    frappe.db.set_value("Customer", customer_id, "disabled", is_disabled)
    
    return {"id": customer_id, "status": action}
