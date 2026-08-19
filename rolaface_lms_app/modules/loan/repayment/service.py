from rolaface_lms_app.modules.loan.restructure.utils import _add_periods
import frappe
from typing import Tuple, Dict,List, Any
from .constant import ALLOWED_PAYMENT_FIELD, RETURN_FIELDS_GET_ALL, RETURN_FIELDS_GET_BY_ID, ALLOWED_SORT_FIELDS 
from frappe.utils import add_months, getdate
import json

def create_payment(data: Dict[str, Any]):
    payment_doc = frappe.new_doc("Loan Repayment")
    for field in ALLOWED_PAYMENT_FIELD:
        if field in data and data.get(field) is not None:
            payment_doc.set(field, data.get(field))
    frappe.error_log(f"Payment Doc --> {payment_doc}")
    payment_doc.insert(ignore_permissions=True)


def get_loan_repayment_account(search_term: str = "", limit: int = 20, initiated_restructure: bool = False) -> List[Dict[str, Any]]:

    search_term = (search_term or "").strip()
    if not search_term:
        return []

    like_term = f"%{search_term}%"

    matching_customers = frappe.get_all(
        "Customer", filters={"mobile_no": ["like", like_term]}, pluck="name"
    )
    matching_employees = frappe.get_all(
        "Employee", filters={"cell_number": ["like", like_term]}, pluck="name"
    )
    phone_matched_applicants = matching_customers + matching_employees

    or_filters = [
        ["Loan", "name", "like", like_term],
        ["Loan", "applicant", "like", like_term],
    ]
    filters = []
    loan_meta = frappe.get_meta("Loan")

    if initiated_restructure:
        initiated_loans = frappe.get_all("Loan Restructure", filters={"status": "Initiated"}, fields=["loan"])
        initiated_loan_names = [d.loan for d in initiated_loans]
        filters.append(["name", "not in", initiated_loan_names])

    if loan_meta.has_field("applicant_name"):
        or_filters.append(["Loan", "applicant_name", "like", like_term])

    if phone_matched_applicants:
        or_filters.append(["Loan", "applicant", "in", phone_matched_applicants])

    fields = [
        "name as against_loan",
        "applicant",
        "applicant_type",
        "sanctioned_amount",
        "repayment_frequency"
    ]
    if loan_meta.has_field("applicant_name"):
        fields.append("applicant_name")

    emi_field = next(
        (f for f in ("monthly_repayment_amount", "repayment_amount", "emi_amount")
         if loan_meta.has_field(f)),
        None,
    )
    if emi_field:
        fields.append(f"{emi_field} as emi")


    has_repayment_start_date = loan_meta.has_field("repayment_start_date")
    has_repayment_periods = loan_meta.has_field("repayment_periods")

    if has_repayment_start_date:
        fields.append("repayment_start_date")
    if has_repayment_periods:
        fields.append("repayment_periods")

    loans = frappe.get_list(
        "Loan",
        or_filters=or_filters,
        filters = filters,
        fields=fields,
        limit_page_length=limit,
        order_by="modified desc",
    )
    if has_repayment_start_date and has_repayment_periods:
        for loan in loans:
            start_date = loan.get("repayment_start_date")
            periods = loan.get("repayment_periods")

            if start_date and periods:
                loan["maturity_date"] = _add_periods(start_date, periods,loan.get("repayment_frequency"))
            else:
                loan["maturity_date"] = None

    return _attach_phone_numbers(loans)


def _attach_phone_numbers(loans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    customer_ids = [l["applicant"] for l in loans if l.get("applicant_type") == "Customer"]
    employee_ids = [l["applicant"] for l in loans if l.get("applicant_type") == "Employee"]

    phone_map: Dict[str, str] = {}

    if customer_ids:
        for row in frappe.get_all(
            "Customer", filters={"name": ["in", customer_ids]}, fields=["name", "mobile_no"]
        ):
            phone_map[row["name"]] = row.get("mobile_no")

    if employee_ids:
        for row in frappe.get_all(
            "Employee", filters={"name": ["in", employee_ids]}, fields=["name", "cell_number"]
        ):
            phone_map[row["name"]] = row.get("cell_number")

    for loan in loans:
        loan["phone_number"] = phone_map.get(loan.get("applicant"))
        loan.setdefault("emi", None)

    return loans

def get_loan_repayment_by_id(repayment_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Repayment", repayment_id):
        raise frappe.DoesNotExistError(f"Loan Repayment '{repayment_id}' does not exist.")

    repayment_doc = frappe.get_doc("Loan Repayment", repayment_id)
    result = {field: repayment_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    return result


def get_loan_repayments(args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc") -> Tuple[list, int, int]:
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

    safe_filters = {}
    if args.get("applicant"):
        safe_filters["applicant"] = args.get("applicant")
    if args.get("against_loan"):
        safe_filters["against_loan"] = args.get("against_loan")
    if args.get("status"):
        status = args.get("status")
        if isinstance(status, str):
            try:
                status = json.loads(status)
            except json.JSONDecodeError:
                status = [status]
        LABEL_TO_DOCSTATUS = {v.lower(): k for k, v in DOCSTATUS_LABELS.items()}

        normalized_status = []
        for s in status:
            if isinstance(s, str) and not s.isdigit():
                mapped = LABEL_TO_DOCSTATUS.get(s.strip().lower())
                if mapped is None:
                    frappe.throw(f"Invalid status value: '{s}'")
                normalized_status.append(mapped)
            else:
                normalized_status.append(int(s))

        safe_filters["docstatus"] = ["in", normalized_status]
    
    if args.get("repayment_type"):
        repayment_type = args.get("repayment_type")
        if isinstance(repayment_type, str):
            try:
                repayment_type = json.loads(repayment_type)
            except json.JSONDecodeError:
                repayment_type = [repayment_type]
        
        safe_filters["repayment_type"] = ["in",repayment_type]

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan Repayment`.`{sort_by}` {sort_order_clean}"

    repayments = frappe.get_all(
        "Loan Repayment",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_repayments = len(
        frappe.get_all(
            "Loan Repayment",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_repayments + page_size - 1) // page_size

    return repayments, total_repayments, total_pages


def update_loan_repayment(repayment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists("Loan Repayment", repayment_id):
        raise frappe.DoesNotExistError(f"Loan Repayment '{repayment_id}' does not exist.")

    repayment_doc = frappe.get_doc("Loan Repayment", repayment_id)

    if repayment_doc.docstatus == 1:
        raise frappe.ValidationError(f"Cannot update submitted Loan Repayment '{repayment_id}'.")

    has_changes = False
    for field in ALLOWED_PAYMENT_FIELD:
        if field in data and data.get(field) is not None:
            if repayment_doc.get(field) != data.get(field):
                repayment_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        repayment_doc.save(ignore_permissions=True)

    return get_loan_repayment_by_id(repayment_doc.name)


def delete_loan_repayment(repayment_id: str):
    if not frappe.db.exists("Loan Repayment", repayment_id):
        raise frappe.DoesNotExistError(f"Loan Repayment '{repayment_id}' does not exist.")

    docstatus = frappe.db.get_value("Loan Repayment", repayment_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(f"Cannot delete a submitted Loan Repayment '{repayment_id}'. Cancel it first.")

    frappe.delete_doc("Loan Repayment", repayment_id, ignore_permissions=True)


# def process_approval(repayment_doc):
#     if repayment_doc.docstatus == 1:
#         raise frappe.ValidationError("Loan Repayment is already approved.")
#     if repayment_doc.docstatus == 2:
#         raise frappe.ValidationError("Cannot approve a cancelled Loan Repayment. Please amend it first.")

#     repayment_doc.submit()

#     return {
#         "id": repayment_doc.name,
#         "status": repayment_doc.status,
#         "docstatus": repayment_doc.docstatus
#     }


# def process_cancellation(repayment_doc):
#     if repayment_doc.docstatus == 2:
#         raise frappe.ValidationError("Loan Repayment is already cancelled.")
#     if repayment_doc.docstatus == 0:
#         raise frappe.ValidationError("Cannot cancel a Draft Loan Repayment. Submit it first.")

#     repayment_doc.cancel()

#     return {
#         "id": repayment_doc.name,
#         "status": repayment_doc.status,
#         "docstatus": repayment_doc.docstatus
#     }


# def process_amendment(repayment_doc):
#     if repayment_doc.docstatus == 0:
#         raise frappe.ValidationError("Loan Repayment is already in Draft state.")
#     if repayment_doc.docstatus == 1:
#         raise frappe.ValidationError("Cannot amend an approved Loan Repayment. Cancel it first.")

#     amended_doc = frappe.copy_doc(repayment_doc)
#     amended_doc.amended_from = repayment_doc.name
#     amended_doc.docstatus = 0

#     amended_doc.insert()

#     return {
#         "id": amended_doc.name,
#         "status": amended_doc.status,
#         "docstatus": amended_doc.docstatus,
#         "amended_from": amended_doc.amended_from
#     }
DOCSTATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}


def process_approval(repayment_doc):
    if repayment_doc.docstatus == 1:
        raise frappe.ValidationError("Loan Repayment is already approved.")
    if repayment_doc.docstatus == 2:
        raise frappe.ValidationError("Cannot approve a cancelled Loan Repayment. Please amend it first.")

    repayment_doc.submit()

    return {
        "id": repayment_doc.name,
        "status": DOCSTATUS_LABELS.get(repayment_doc.docstatus),
        "docstatus": repayment_doc.docstatus
    }


def process_cancellation(repayment_doc):
    if repayment_doc.docstatus == 2:
        raise frappe.ValidationError("Loan Repayment is already cancelled.")
    if repayment_doc.docstatus == 0:
        raise frappe.ValidationError("Cannot cancel a Draft Loan Repayment. Submit it first.")

    repayment_doc.cancel()

    return {
        "id": repayment_doc.name,
        "status": DOCSTATUS_LABELS.get(repayment_doc.docstatus),
        "docstatus": repayment_doc.docstatus
    }


def process_amendment(repayment_doc):
    if repayment_doc.docstatus == 0:
        raise frappe.ValidationError("Loan Repayment is already in Draft state.")
    if repayment_doc.docstatus == 1:
        raise frappe.ValidationError("Cannot amend an approved Loan Repayment. Cancel it first.")

    amended_doc = frappe.copy_doc(repayment_doc)
    amended_doc.amended_from = repayment_doc.name
    amended_doc.docstatus = 0

    amended_doc.insert()

    return {
        "id": amended_doc.name,
        "status": DOCSTATUS_LABELS.get(amended_doc.docstatus),
        "docstatus": amended_doc.docstatus,
        "amended_from": amended_doc.amended_from
    }

def update_loan_repayment_status(repayment_id: str, action: str):
    repayment_doc = frappe.get_doc("Loan Repayment", repayment_id)

    if not frappe.has_permission("Loan Repayment", "write", repayment_doc):
        raise frappe.PermissionError("No permission to modify this Loan Repayment.")

    if action == "approved":
        return process_approval(repayment_doc)

    elif action == "cancelled":
        return process_cancellation(repayment_doc)

    elif action == "amend":
        return process_amendment(repayment_doc)

    else:
        raise frappe.ValidationError("Invalid action. Allowed: approved, cancelled, amend")