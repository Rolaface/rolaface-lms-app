import frappe
from typing import Tuple, Dict, Any
from .utils import build_loan_disbursement_filters, validate_loan_disbursement_payload, sync_loan_disbursement_charges
from .constant import ALLOWED_DISBURSEMENT_FIELDS, RETURN_FIELDS_GET_ALL, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS

def create_loan_disbursement(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("company"):
        data["company"] = frappe.defaults.get_user_default("Company")
    validate_loan_disbursement_payload(data, is_update=False)

    loan_disbursement_doc = frappe.new_doc("Loan Disbursement")
    
    for field in ALLOWED_DISBURSEMENT_FIELDS:
        if field in data and data.get(field) is not None:
            loan_disbursement_doc.set(field, data.get(field))

    loan_disbursement_doc.set("custom_disbursement_metadata", [])
    loan_disbursement_doc.append("custom_disbursement_metadata", {
                                                                    "top_up": int(data.get("top_up") or 0),
                                                                    "top_up_details": data.get("top_up_details"),
                                                                })
    sync_loan_disbursement_charges(loan_disbursement_doc, data.get("loan_disbursement_charges"))
    loan_disbursement_doc.set_missing_values()    
    loan_disbursement_doc.insert(ignore_permissions=True)
    return get_loan_disbursement_by_id(loan_disbursement_doc.name)


def update_loan_disbursement(disbursement_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Disbursement", disbursement_id):
        raise frappe.DoesNotExistError(f"Loan Disbursement '{disbursement_id}' does not exist.")

    loan_disbursement_doc = frappe.get_doc("Loan Disbursement", disbursement_id)
    
    if loan_disbursement_doc.docstatus == 1:
        raise frappe.ValidationError(f"Cannot update submitted Loan Disbursement '{disbursement_id}'.")

    validate_loan_disbursement_payload(data, is_update=True)
    has_changes = False

    for field in ALLOWED_DISBURSEMENT_FIELDS:
        if field in data and data.get(field) is not None:
            if loan_disbursement_doc.get(field) != data.get(field):
                loan_disbursement_doc.set(field, data.get(field))
                has_changes = True

    charges_payload = data.get("loan_disbursement_charges")
    if charges_payload is not None:
        if sync_loan_disbursement_charges(loan_disbursement_doc, charges_payload):
            has_changes = True

    if "top_up" in data or "top_up_details" in data:
        loan_disbursement_doc.set("custom_disbursement_metadata", [])
        loan_disbursement_doc.append("custom_disbursement_metadata", {
            "top_up": int(data.get("top_up") or 0),
            "top_up_details": data.get("top_up_details"),
        })
        has_changes = True

    if has_changes:
        loan_disbursement_doc.save(ignore_permissions=True)

    return get_loan_disbursement_by_id(loan_disbursement_doc.name)


def get_loan_disbursement_by_id(disbursement_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Disbursement", disbursement_id):
        raise frappe.DoesNotExistError(f"Loan Disbursement '{disbursement_id}' does not exist.")
        
    loan_disbursement_doc = frappe.get_doc("Loan Disbursement", disbursement_id)
    result = {field: loan_disbursement_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    
    charges = []
    disbursement_charges_table = loan_disbursement_doc.get("loan_disbursement_charges") or [] 

    top_up = 0
    top_up_details = None
    disbursement_metadata = loan_disbursement_doc.custom_disbursement_metadata[0] if loan_disbursement_doc.custom_disbursement_metadata else None 
    if disbursement_metadata:
        top_up = disbursement_metadata.get("top_up")
        if top_up:
            top_up_details = disbursement_metadata.get("top_up_details")
    for row in disbursement_charges_table:
        charges.append({
            "name": row.name,
            "charge": row.charge,
            "amount": row.amount,
            "account": row.account,
            "treatment_of_charge": row.treatment_of_charge
        })
        
    result["loan_disbursement_charges"] = charges
    result["top_up"] = top_up
    result["top_up_details"] = top_up_details
    return result


def get_loan_disbursements(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []
    
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["against_loan", "like", search_term],
            ["applicant", "like", search_term]
        ]

    safe_filters = build_loan_disbursement_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Disbursement`.`{sort_by}` {sort_order_clean}"

    disbursements = frappe.get_all(
        "Loan Disbursement",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_disbursements = len(
        frappe.get_all(
            "Loan Disbursement",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_disbursements + page_size - 1) // page_size

    return disbursements, total_disbursements, total_pages


def delete_loan_disbursement(disbursement_id: str):
    if not frappe.db.exists("Loan Disbursement", disbursement_id):
        raise frappe.DoesNotExistError(f"Loan Disbursement '{disbursement_id}' does not exist.")
        
    docstatus = frappe.db.get_value("Loan Disbursement", disbursement_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete a submitted Loan Disbursement '{disbursement_id}'. Cancel it first.")

    frappe.delete_doc("Loan Disbursement", disbursement_id, ignore_permissions=True)


def process_approval(loan_disbursement_doc):
    if loan_disbursement_doc.docstatus == 1:
        raise frappe.ValidationError("Loan Disbursement is already approved.")
    if loan_disbursement_doc.docstatus == 2:
        raise frappe.ValidationError("Cannot approve a cancelled Loan Disbursement. Please amend it first.")

    loan_disbursement_doc.submit()

    return {
        "id": loan_disbursement_doc.name,
        "status": loan_disbursement_doc.status,
        "docstatus": loan_disbursement_doc.docstatus
    }

def process_cancellation(loan_disbursement_doc):
    if loan_disbursement_doc.docstatus == 2:
        raise frappe.ValidationError("Loan Disbursement is already cancelled.")
    if loan_disbursement_doc.docstatus == 0:
        raise frappe.ValidationError("Cannot cancel a Draft Loan Disbursement. Submit it first.")

    loan_disbursement_doc.cancel()

    return {
        "id": loan_disbursement_doc.name,
        "status": loan_disbursement_doc.status,
        "docstatus": loan_disbursement_doc.docstatus
    }

def process_amendment(loan_disbursement_doc):
    if loan_disbursement_doc.docstatus == 0:
        raise frappe.ValidationError("Loan Disbursement is already in Draft state.")
    if loan_disbursement_doc.docstatus == 1:
        raise frappe.ValidationError("Cannot amend an approved Loan Disbursement. Cancel it first.")

    amended_doc = frappe.copy_doc(loan_disbursement_doc)
    amended_doc.amended_from = loan_disbursement_doc.name
    amended_doc.docstatus = 0
    
    amended_doc.insert()

    return {
        "id": amended_doc.name,
        "status": amended_doc.status,
        "docstatus": amended_doc.docstatus,
        "amended_from": amended_doc.amended_from
    }

def update_loan_disbursement_status(disbursement_id: str, action: str):
    loan_disbursement_doc = frappe.get_doc("Loan Disbursement", disbursement_id)

    if not frappe.has_permission("Loan Disbursement", "write", loan_disbursement_doc):
        raise frappe.PermissionError("No permission to modify this Loan Disbursement.")

    if action == "approved":
        return process_approval(loan_disbursement_doc)
        
    elif action == "cancelled":
        return process_cancellation(loan_disbursement_doc)
        
    elif action == "amend":
        return process_amendment(loan_disbursement_doc)
        
    else:
        raise frappe.ValidationError("Invalid action. Allowed: approved, cancelled, amend")