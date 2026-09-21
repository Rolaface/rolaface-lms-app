import frappe
import json
import re
from typing import Dict, Any, List
from frappe.utils import cint

from .constant import CHILD_TABLE_FIELDS, FIELD_MAPPING, TABLE_MAPPING


def transform_payload_to_db(data: Dict[str, Any]) -> Dict[str, Any]:
    db_payload = data.copy()

    for table_name, allowed_fields in CHILD_TABLE_FIELDS.items():
        if isinstance(db_payload.get(table_name), list):
            db_payload[table_name] = [
                {field: value for field, value in row.items() if field in allowed_fields}
                for row in db_payload[table_name]
            ]
    
    for api_key, db_key in FIELD_MAPPING.items():
        if api_key in db_payload:
            db_payload[db_key] = db_payload.pop(api_key)

    for api_table, db_table in TABLE_MAPPING.items():
        if api_table in db_payload:
            db_payload[db_table] = db_payload.pop(api_table)

    return db_payload


def transform_db_to_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Translates internal Frappe schema to clean frontend API keys."""
    api_payload = data.copy()

    for api_key, db_key in FIELD_MAPPING.items():
        if db_key in api_payload:
            api_payload[api_key] = api_payload.pop(db_key)

    for api_table, db_table in TABLE_MAPPING.items():
        if db_table in api_payload:
            api_payload[api_table] = api_payload.pop(db_table)

    rm_id = api_payload.get("relationship_manager")
    if rm_id:
        full_name = frappe.db.get_value("User", rm_id, "full_name")
        api_payload["relationship_manager_name"] = full_name or None
    else:
        api_payload["relationship_manager_name"] = None

    return api_payload


def validate_customer_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = ["customer_name", "customer_type", "customer_group"]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    email = data.get("email_id")
    if email:
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        if not re.fullmatch(pattern, email):
            raise frappe.ValidationError(f"Invalid email format: {email}")

    customer_type = data.get("customer_type")
    if customer_type:
        valid_types = {"Individual", "Company", "Partnership"}
        if customer_type not in valid_types:
            raise frappe.ValidationError(f"Invalid customer_type. Allowed: {', '.join(valid_types)}")

    tpin = data.get("tax_id")
    if tpin:
        filters = {"tax_id": tpin}
        if is_update and data.get("name"):
            filters["name"] = ["!=", data.get("name")]
        
        if frappe.db.exists("Customer", filters):
            raise frappe.exceptions.DuplicateEntryError(f"Customer with tax_id (TPIN) {tpin} already exists.")

    for field in ("addresses", "contacts"):
        if field not in data:
            continue
        items = data[field]
        if not isinstance(items, list):
            raise frappe.ValidationError(f"'{field}' must be a list.")
        if not all(isinstance(item, dict) for item in items):
            raise frappe.ValidationError(f"Each item in '{field}' must be an object.")

    if "contacts" in data and any(not item.get("first_name") for item in data["contacts"]):
        raise frappe.ValidationError("Each contact must include first_name.")


def sync_addresses(parent_doc, addresses_data: list, is_update: bool = False):
    if addresses_data is None:
        return

    addresses_data = addresses_data or []

    link_doctype = parent_doc.doctype
    link_name = parent_doc.name
    doc_title = parent_doc.name

    existing_links = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Address", "link_doctype": link_doctype, "link_name": link_name},
        pluck="parent",
    )
    existing_addresses = set(existing_links)
    processed_addresses = set()
    primary_address = None

    for i, addr in enumerate(addresses_data):
        addr_id = addr.get("name")
        is_primary = 1 if addr.get("is_primary_address") or i == 0 else 0
        country = addr.get("country") or frappe.defaults.get_global_default("country") or "Zambia"

        if is_update and addr_id:
            if addr_id not in existing_addresses:
                raise frappe.ValidationError(f"Address '{addr_id}' is not linked to customer '{link_name}'.")
            if not frappe.db.exists("Address", addr_id):
                raise frappe.DoesNotExistError(f"Address '{addr_id}' does not exist.")
            address = frappe.get_doc("Address", addr_id)
            address.address_title = doc_title
            address.address_type = addr.get("address_type", address.address_type)
            address.address_line1 = addr.get("address_line1", address.address_line1)
            address.address_line2 = addr.get("address_line2", address.address_line2)
            address.city = addr.get("city", address.city)
            address.state = addr.get("state", address.state)
            address.pincode = addr.get("pincode", address.pincode)
            address.country = country.title()
            address.is_primary_address = is_primary
            address.is_shipping_address = 1 if addr.get("is_shipping_address") else 0

            if not any(l.link_doctype == link_doctype and l.link_name == link_name for l in address.links):
                address.append("links", {"link_doctype": link_doctype, "link_name": link_name})

            address.save()
            processed_addresses.add(address.name)
        else:
            address = frappe.get_doc({
                "doctype": "Address",
                "address_title": doc_title,
                "address_type": addr.get("address_type", "Billing"),
                "address_line1": addr.get("address_line1"),
                "address_line2": addr.get("address_line2"),
                "city": addr.get("city"),
                "state": addr.get("state"),
                "pincode": addr.get("pincode"),
                "country": country.title(),
                "email_id": getattr(parent_doc, "email_id", ""),
                "phone": getattr(parent_doc, "mobile_no", ""),
                "is_primary_address": is_primary,
                "is_shipping_address": 1 if addr.get("is_shipping_address") else 0,
                "links": [{"link_doctype": link_doctype, "link_name": link_name}],
            }).insert()
            processed_addresses.add(address.name)

        if is_primary:
            primary_address = address.name

    if primary_address and frappe.db.has_column(parent_doc.doctype, "customer_primary_address"):
        parent_doc.db_set("customer_primary_address", primary_address, update_modified=True)
    elif is_update and frappe.db.has_column(parent_doc.doctype, "customer_primary_address"):
        parent_doc.db_set("customer_primary_address", None, update_modified=True)

    if is_update:
        for doc_name in (existing_addresses - processed_addresses):
            doc = frappe.get_doc("Address", doc_name)
            doc.links = [l for l in doc.links if not (l.link_doctype == link_doctype and l.link_name == link_name)]
            if doc.links:
                doc.save()
            else:
                doc.disabled = 1
                doc.save()


def sync_contacts(parent_doc, contacts_data: list, is_update: bool = False):
    if contacts_data is None:
        return

    contacts_data = contacts_data or []

    link_doctype = parent_doc.doctype
    link_name = parent_doc.name

    existing_links = frappe.get_all(
        "Dynamic Link", 
        filters={"parenttype": "Contact", "link_doctype": link_doctype, "link_name": link_name}, 
        pluck="parent"
    )
    existing_contacts = set(existing_links)
    processed_contacts = set()

    primary_contact = None
    primary_email = ""
    primary_mobile = ""

    for i, contact_info in enumerate(contacts_data):
        contact_id = contact_info.get("name")
        first_name = contact_info.get("first_name")
        if not first_name:
            continue

        is_primary = 1 if contact_info.get("is_primary_contact") or i == 0 else 0
        email = contact_info.get("email_id")
        mobile = contact_info.get("mobile_no")

        if is_update and contact_id and contact_id in existing_contacts:
            contact_doc = frappe.get_doc("Contact", contact_id)
            contact_doc.first_name = first_name
            contact_doc.last_name = contact_info.get("last_name", "")
            contact_doc.salutation = contact_info.get("salutation", contact_doc.salutation)
            contact_doc.designation = contact_info.get("designation", contact_doc.designation)
            contact_doc.is_primary_contact = is_primary
            contact_doc.is_billing_contact = 1 if contact_info.get("is_billing_contact") else 0
            
            contact_doc.set("email_ids", [])
            contact_doc.set("phone_nos", [])
            if email: contact_doc.append("email_ids", {"email_id": email, "is_primary": 1})
            if mobile: contact_doc.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
            
            contact_doc.save()
            processed_contacts.add(contact_doc.name)
        else:
            if is_update and contact_id:
                raise frappe.ValidationError(f"Contact '{contact_id}' is not linked to customer '{link_name}'.")
            contact_doc = frappe.get_doc({
                "doctype": "Contact",
                "first_name": first_name,
                "last_name": contact_info.get("last_name", ""),
                "salutation": contact_info.get("salutation", ""),
                "designation": contact_info.get("designation", ""),
                "is_primary_contact": is_primary,
                "is_billing_contact": 1 if contact_info.get("is_billing_contact") else 0,
                "links": [{"link_doctype": link_doctype, "link_name": link_name}]
            })
            if email: contact_doc.append("email_ids", {"email_id": email, "is_primary": 1})
            if mobile: contact_doc.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
            
            contact_doc.insert()
            processed_contacts.add(contact_doc.name)

        if is_primary:
            primary_contact = contact_doc.name
            primary_email = email
            primary_mobile = mobile

    updates = {}
    if getattr(parent_doc, "customer_primary_contact", None) != primary_contact:
        updates["customer_primary_contact"] = primary_contact
    if getattr(parent_doc, "email_id", None) != primary_email:
        updates["email_id"] = primary_email
    if getattr(parent_doc, "mobile_no", None) != primary_mobile:
        updates["mobile_no"] = primary_mobile
    
    if updates:
        parent_doc.db_set(updates, update_modified=True)

    if is_update:
        for doc_name in (existing_contacts - processed_contacts):
            doc = frappe.get_doc("Contact", doc_name)
            doc.links = [l for l in doc.links if not (l.link_doctype == link_doctype and l.link_name == link_name)]
            doc.flags.ignore_links = True
            if doc.links:
                doc.save()
            else:
                try: frappe.delete_doc("Contact", doc.name, force=True)
                except frappe.exceptions.LinkExistsError: pass


def get_linked_addresses(link_doctype: str, link_name: str) -> List[Dict]:
    return frappe.get_all(
        "Address",
        filters={"link_doctype": link_doctype, "link_name": link_name},
        fields=[
            "name", "address_type", "address_line1", "address_line2",
            "city", "state", "pincode", "country",
            "is_primary_address", "is_shipping_address"
        ]
    )

def get_linked_contacts(link_doctype: str, link_name: str) -> List[Dict]:
    linked_contact_names = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Contact", "link_doctype": link_doctype, "link_name": link_name},
        pluck="parent"
    )
    if not linked_contact_names: return []

    return frappe.get_all(
        "Contact",
        filters={"name": ("in", linked_contact_names)},
        fields=[
            "name", "first_name", "last_name", "salutation", "designation",
            "email_id", "mobile_no", "is_primary_contact", "is_billing_contact"
        ]
    )

def build_customer_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    filters = {}
    if not args:
        return filters

    if "status" in args:
        status = str(args.get("status")).strip().lower()
        if status == "active":
            filters["disabled"] = 0
        elif status == "inactive":
            filters["disabled"] = 1

    boolean_fields = ["disabled", "is_frozen", "is_internal_customer", "is_npa", "so_required", "dn_required"]
    for field in boolean_fields:
        if args.get(field) is not None:
            filters[field] = cint(args.get(field))

    list_fields = [
        "customer_type", "customer_group", "territory", "gender", 
        "default_currency", "tax_category", "tax_withholding_category",
        "loyalty_program", "loyalty_program_tier", "account_manager", 
        "default_sales_partner", "market_segment", "industry", "language"
    ]
    
    for field in list_fields:
        if args.get(field):
            val = args.get(field)
            if isinstance(val, str) and val.startswith("["):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            
            if isinstance(val, list):
                filters[field] = ["in", val]
            else:
                filters[field] = val

    from_date = args.get("from_date")
    to_date = args.get("to_date")
    
    if from_date and to_date:
        filters["creation"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["creation"] = [">=", from_date]
    elif to_date:
        filters["creation"] = ["<=", to_date]

    return filters
