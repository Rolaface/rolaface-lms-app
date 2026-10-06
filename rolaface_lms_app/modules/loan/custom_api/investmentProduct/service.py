import frappe
from typing import Tuple, Dict, Any
from .constant import (
    DOCTYPE,
    ALLOWED_INVESTMENT_PRODUCT_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
)
from .utils import _validate_investment_product_payload, _build_investment_product_filters


def _product_name_taken(product_name: str, exclude_id: str = None) -> bool:
    """The document name is auto-generated, so uniqueness is checked on product_name."""
    filters = {"product_name": str(product_name).strip()}
    if exclude_id:
        filters["name"] = ["!=", exclude_id]
    return bool(frappe.db.exists(DOCTYPE, filters))


def create_investment_product(data: Dict[str, Any]) -> Dict[str, Any]:
    _validate_investment_product_payload(data, is_update=False)

    if _product_name_taken(data.get("product_name")):
        raise frappe.DuplicateEntryError(
            f"Investment Product '{data.get('product_name')}' already exists."
        )

    product_doc = frappe.new_doc(DOCTYPE)

    for field in ALLOWED_INVESTMENT_PRODUCT_FIELDS:
        if field in data and data.get(field) is not None:
            product_doc.set(field, data.get(field))

    product_doc.insert(ignore_permissions=True)
    return get_investment_product_by_id(product_doc.name)


def update_investment_product(product_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, product_id):
        raise frappe.DoesNotExistError(f"Investment Product '{product_id}' does not exist.")

    product_doc = frappe.get_doc(DOCTYPE, product_id)

    _validate_investment_product_payload(data, is_update=True)

    if data.get("product_name") and _product_name_taken(data.get("product_name"), exclude_id=product_id):
        raise frappe.DuplicateEntryError(
            f"Investment Product '{data.get('product_name')}' already exists."
        )

    has_changes = False

    for field in ALLOWED_INVESTMENT_PRODUCT_FIELDS:
        if field in data and data.get(field) is not None:
            if product_doc.get(field) != data.get(field):
                product_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        product_doc.save(ignore_permissions=True)

    return get_investment_product_by_id(product_doc.name)


def get_investment_product_by_id(product_id: str) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, product_id):
        raise frappe.DoesNotExistError(f"Investment Product '{product_id}' does not exist.")

    product_doc = frappe.get_doc(DOCTYPE, product_id)
    result = {field: product_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    return result


def get_investment_products(
    args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc"
) -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["product_name", "like", search_term],
        ]

    safe_filters = _build_investment_product_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tab{DOCTYPE}`.`{sort_by}` {sort_order_clean}"

    products = frappe.get_all(
        DOCTYPE,
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_records = len(
        frappe.get_all(
            DOCTYPE,
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_records + page_size - 1) // page_size

    return products, total_records, total_pages


def delete_investment_product(product_id: str):
    if not frappe.db.exists(DOCTYPE, product_id):
        raise frappe.DoesNotExistError(f"Investment Product '{product_id}' does not exist.")

    frappe.delete_doc(DOCTYPE, product_id, ignore_permissions=True)


def toggle_investment_product_status(product_id: str, disable_flag: int):
    if not frappe.db.exists(DOCTYPE, product_id):
        raise frappe.DoesNotExistError(f"Investment Product '{product_id}' does not exist.")

    product_doc = frappe.get_doc(DOCTYPE, product_id)

    if product_doc.disabled == disable_flag:
        action = "disabled" if disable_flag == 1 else "enabled"
        raise frappe.ValidationError(
            f"Investment Product '{product_doc.product_name}' is already {action}."
        )

    product_doc.disabled = disable_flag
    product_doc.save(ignore_permissions=True)

    return {
        "id": product_doc.name,
        "product_name": product_doc.product_name,
        "disabled": product_doc.disabled,
    }