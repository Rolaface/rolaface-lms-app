import frappe
from frappe.utils import cint, flt
from .utils import (
    build_loan_product_filters,
    validate_loan_product_payload,
    sync_loan_charges
)

from .constant import (
    ALLOWED_LOAN_PRODUCT_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS
)

def create_loan_product(data: dict):
    validate_loan_product_payload(data, is_update=False)

    product = frappe.new_doc("Loan Product")
    
    for field in ALLOWED_LOAN_PRODUCT_FIELDS:
        if field in data and data.get(field) is not None:
            product.set(field, data.get(field))

    if not product.get("company"):
        product.company = frappe.defaults.get_user_default("Company")

    sync_loan_charges(product, data.get("loan_charges"))
    product.insert(ignore_permissions=True)
    return get_loan_product_by_id(product.name)


def update_loan_product(product_id: str, data: dict):
    if not frappe.db.exists("Loan Product", product_id):
        raise frappe.DoesNotExistError(f"Loan Product '{product_id}' does not exist.")

    data["name"] = product_id
    validate_loan_product_payload(data, is_update=True)
    
    product = frappe.get_doc("Loan Product", product_id)
    has_changes = False

    for field in ALLOWED_LOAN_PRODUCT_FIELDS:
        if field in data and data.get(field) is not None:
            if product.get(field) != data.get(field):
                product.set(field, data.get(field))
                has_changes = True

    if "loan_charges" in data:
        if sync_loan_charges(product, data.get("loan_charges")):
            has_changes = True

    if has_changes:
        product.save(ignore_permissions=True)

    return get_loan_product_by_id(product.name)


def get_loan_product_by_id(product_id: str):
    if not frappe.db.exists("Loan Product", product_id):
        raise frappe.DoesNotExistError(f"Loan Product '{product_id}' does not exist.")
        
    doc = frappe.get_doc("Loan Product", product_id)
    
    result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    
    charges = []
    for row in doc.get("loan_charges", []):
        charges.append({
            "name": row.name,
            "charge_type": row.charge_type,
            "charge_based_on": row.charge_based_on,
            "percentage": row.percentage,
            "amount": row.amount,
            "income_account": row.income_account,
            "waiver_account": row.waiver_account,
            "suspense_account": row.suspense_account,
            "receivable_account": row.receivable_account,
            "write_off_account": row.write_off_account,
        })
        
    result["loan_charges"] = charges
    return result


def get_loan_products(args: dict, page: int, page_size: int, sort_by="creation", sort_order="desc"):
    start = (page - 1) * page_size
    or_filters = []
    
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["product_code", "like", search_term],
            ["product_name", "like", search_term],
            ["loan_category", "like", search_term],
        ]

    safe_filters = build_loan_product_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Product`.`{sort_by}` {sort_order_clean}"

    products = frappe.get_all(
        "Loan Product",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_products = len(
        frappe.get_all(
            "Loan Product",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_products + page_size - 1) // page_size

    return products, total_products, total_pages


def delete_loan_product(product_id: str):
    if not frappe.db.exists("Loan Product", product_id):
        raise frappe.DoesNotExistError(f"Loan Product '{product_id}' does not exist.")
        
    linked_loans = frappe.db.count("Loan", {"loan_product": product_id, "docstatus": ["!=", 2]})
    if linked_loans > 0:
        raise frappe.ValidationError(f"Cannot delete Loan Product '{product_id}' because it is linked to {linked_loans} active loan(s). Disable it instead.")

    frappe.delete_doc("Loan Product", product_id, ignore_permissions=True)


def toggle_loan_product_status(product_id: str, disable_flag: int):
    if not frappe.db.exists("Loan Product", product_id):
        raise frappe.DoesNotExistError(f"Loan Product '{product_id}' does not exist.")
    
    product = frappe.get_doc("Loan Product", product_id)
    
    if product.disabled == disable_flag:
        action = "disabled" if disable_flag == 1 else "enabled"
        raise frappe.ValidationError(f"Loan Product '{product.product_name}' is already {action}.")

    product.disabled = disable_flag
    product.save(ignore_permissions=True)
    
    return {
        "id": product.name,
        "product_code": product.product_code,
        "product_name": product.product_name,
        "disabled": product.disabled
    }