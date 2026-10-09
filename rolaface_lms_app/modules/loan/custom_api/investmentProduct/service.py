import frappe
from typing import Tuple, Dict, Any
from .constant import (
    DOCTYPE,
    ALLOWED_INVESTMENT_PRODUCT_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
    PRODUCT_CODE_FIELD,
)
from .utils import _validate_investment_product_payload, _build_investment_product_filters


def _product_name_taken(product_name: str, exclude_id: str = None) -> bool:
    """The document name is auto-generated, so uniqueness is checked on product_name."""
    filters = {"product_name": str(product_name).strip()}
    if exclude_id:
        filters["name"] = ["!=", exclude_id]
    return bool(frappe.db.exists(DOCTYPE, filters))


def _normalize_product_code(code) -> str:
    return str(code or "").strip().upper()


def create_investment_product(data: Dict[str, Any]) -> Dict[str, Any]:
    values = {f: data.get(f) for f in ALLOWED_INVESTMENT_PRODUCT_FIELDS if f in data}
    if values.get(PRODUCT_CODE_FIELD) is not None:
        values[PRODUCT_CODE_FIELD] = _normalize_product_code(values[PRODUCT_CODE_FIELD])

    _validate_investment_product_payload(values)

    if _product_name_taken(values["product_name"]):
        raise frappe.DuplicateEntryError(f"Investment Product '{values['product_name']}' already exists.")
    if frappe.db.exists(DOCTYPE, {PRODUCT_CODE_FIELD: values[PRODUCT_CODE_FIELD]}):
        raise frappe.DuplicateEntryError(f"Product Code '{values[PRODUCT_CODE_FIELD]}' is already used.")

    product_doc = frappe.new_doc(DOCTYPE)
    for field, value in values.items():
        if value is not None:
            product_doc.set(field, value)

    product_doc.insert(ignore_permissions=True)
    return get_investment_product_by_id(product_doc.name)


def update_investment_product(product_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, product_id):
        raise frappe.DoesNotExistError(f"Investment Product '{product_id}' does not exist.")

    product_doc = frappe.get_doc(DOCTYPE, product_id)

    # Product Code is set once on create and never changes.
    if data.get(PRODUCT_CODE_FIELD) not in (None, "") and product_doc.get(PRODUCT_CODE_FIELD) and (
        _normalize_product_code(data.get(PRODUCT_CODE_FIELD)) != product_doc.get(PRODUCT_CODE_FIELD)
    ):
        raise frappe.ValidationError("Product Code cannot be changed once the product is created.")

    changes = {
        f: data.get(f)
        for f in ALLOWED_INVESTMENT_PRODUCT_FIELDS
        if f in data and f != PRODUCT_CODE_FIELD
    }
    # Products saved before Product Code existed get their code on the first update.
    if not product_doc.get(PRODUCT_CODE_FIELD) and data.get(PRODUCT_CODE_FIELD) not in (None, ""):
        code = _normalize_product_code(data.get(PRODUCT_CODE_FIELD))
        if frappe.db.exists(DOCTYPE, {PRODUCT_CODE_FIELD: code, "name": ["!=", product_id]}):
            raise frappe.DuplicateEntryError(f"Product Code '{code}' is already used.")
        changes[PRODUCT_CODE_FIELD] = code

    # Validate the whole product as it will be saved, so limits and defaults are checked together.
    merged = {f: product_doc.get(f) for f in ALLOWED_INVESTMENT_PRODUCT_FIELDS}
    merged.update(changes)
    _validate_investment_product_payload(merged)

    if changes.get("product_name") and _product_name_taken(changes["product_name"], exclude_id=product_id):
        raise frappe.DuplicateEntryError(f"Investment Product '{changes['product_name']}' already exists.")

    has_changes = False
    for field, value in changes.items():
        if product_doc.get(field) != value:
            product_doc.set(field, value)
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
            ["product_code", "like", search_term],
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