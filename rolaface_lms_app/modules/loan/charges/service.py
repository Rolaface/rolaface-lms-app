import frappe
from typing import Tuple, Dict, Any
from .utils import validate_charge_payload, build_charge_filters
from .constant import ALLOWED_CHARGE_FIELDS, RETURN_FIELDS_GET_ALL, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS

def create_charge(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_charge_payload(data, is_update=False)

    if not data.get("item_code") and data.get("item_name"):
        data["item_code"] = data.get("item_name")

    charge_doc = frappe.new_doc("Item")

    for field in ALLOWED_CHARGE_FIELDS:
        if field in data and data.get(field) is not None:
            charge_doc.set(field, data.get(field))

    charge_doc.insert(ignore_permissions=True)
    return get_charge_by_id(charge_doc.name)


def update_charge(charge_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Item", charge_id):
        raise frappe.DoesNotExistError(f"Charge '{charge_id}' does not exist.")

    charge_doc = frappe.get_doc("Item", charge_id)
    validate_charge_payload(data, is_update=True)

    has_changes = False
    for field in ALLOWED_CHARGE_FIELDS:
        if field in data and data.get(field) is not None:
            if charge_doc.get(field) != data.get(field):
                charge_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        charge_doc.save(ignore_permissions=True)

    return get_charge_by_id(charge_doc.name)


def get_charge_by_id(charge_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Item", charge_id):
        raise frappe.DoesNotExistError(f"Charge '{charge_id}' does not exist.")

    charge_doc = frappe.get_doc("Item", charge_id)
    result = {field: charge_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    return result


def get_charges(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["item_code", "like", search_term],
            ["item_name", "like", search_term]
        ]

    safe_filters = build_charge_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabItem`.`{sort_by}` {sort_order_clean}"

    charges = frappe.get_all(
        "Item",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_charges = len(
        frappe.get_all(
            "Item",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_charges + page_size - 1) // page_size

    return charges, total_charges, total_pages


def delete_charge(charge_id: str):
    if not frappe.db.exists("Item", charge_id):
        raise frappe.DoesNotExistError(f"Charge '{charge_id}' does not exist.")

    frappe.delete_doc("Item", charge_id, ignore_permissions=True)


def toggle_charge_status(charge_id: str, disable_flag: int):
    if not frappe.db.exists("Item", charge_id):
        raise frappe.DoesNotExistError(f"Charge '{charge_id}' does not exist.")
    
    charge = frappe.get_doc("Item", charge_id)
    
    if charge.disabled == disable_flag:
        action = "disabled" if disable_flag == 1 else "enabled"
        raise frappe.ValidationError(f"Charge '{charge.item_name}' is already {action}.")

    charge.disabled = disable_flag
    charge.save(ignore_permissions=True)
    
    return {
        "id": charge.name,
        "item_code": charge.item_code,
        "item_name": charge.item_name,
        "disabled": charge.disabled
    }