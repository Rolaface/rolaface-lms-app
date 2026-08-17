import frappe
from typing import Tuple, Dict, Any
from frappe.utils import flt

from .utils import build_loan_filters, validate_loan_payload, sync_loan_charges, sync_loan_documents
from .constant import (
    ALLOWED_LOAN_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
)

def attach_loan_documents(loan_id: str, documents: list) -> Dict[str, Any]:
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    try:
        sync_loan_documents(loan_id, documents)
        frappe.db.commit()
        return get_loan_by_id(loan_id)
    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        raise e


def create_loan_security_assignment(loan_doc, collaterals: Dict[str, Any]):
    assignment = frappe.new_doc("Loan Security Assignment")
    assignment.loan = loan_doc.name
    assignment.applicant_type = loan_doc.applicant_type
    assignment.applicant = loan_doc.applicant
    assignment.company = loan_doc.company

    assignment.reference_no = collaterals.get("reference_no")
    assignment.description = collaterals.get("description")

    items = collaterals.get("items", [])
    total_val = 0
    for item in items:
        qty = frappe.utils.flt(item.get("qty", 0))
        price = frappe.utils.flt(item.get("loan_security_price", 0))
        amt = qty * price
        total_val += amt

        assignment.append(
            "securities",
            {
                "loan_security": item.get("loan_security"),
                "qty": qty,
                "loan_security_price": price,
                "amount": amt,
            },
        )

    assignment.total_security_value = total_val
    assignment.insert(ignore_permissions=True)


def sync_loan_security_assignment(loan_doc, collaterals: Dict[str, Any]):
    if not collaterals:
        return

    existing_assignments = frappe.get_all(
        "Loan Security Assignment",
        filters={"loan": loan_doc.name, "docstatus": 0},
        limit=1,
    )

    if existing_assignments:
        assignment = frappe.get_doc(
            "Loan Security Assignment", existing_assignments[0].name
        )

        assignment.reference_no = collaterals.get("reference_no")
        assignment.description = collaterals.get("description")

        assignment.set("securities", [])

        items = collaterals.get("items", [])
        for item in items:
            assignment.append(
                "securities",
                {
                    "loan_security": item.get("loan_security"),
                    "qty": item.get("qty"),
                    "loan_security_price": item.get("loan_security_price"),
                },
            )

        assignment.save(ignore_permissions=True)
    else:
        create_loan_security_assignment(loan_doc, collaterals)


def create_loan(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not data.get("company"):
            data["company"] = frappe.defaults.get_user_default("Company")
        validate_loan_payload(data, is_update=False)

        loan = frappe.new_doc("Loan")

        for field in ALLOWED_LOAN_FIELDS:
            if field in data and data.get(field) is not None:
                loan.set(field, data.get(field))

        if data.get("collaterals"):
            loan.is_secured_loan = 1

        sync_loan_charges(loan, data.get("loan_charges"))
        loan.insert(ignore_permissions=True)

        collaterals = data.get("collaterals")
        if collaterals:
            create_loan_security_assignment(loan, collaterals)

        return get_loan_by_id(loan.name)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        raise e


def update_loan(loan_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        loan = frappe.get_doc("Loan", loan_id)

        if loan.docstatus == 1:
            raise frappe.ValidationError(f"Cannot update submitted Loan '{loan_id}'.")

        validate_loan_payload(data, is_update=True)
        has_changes = False

        for field in ALLOWED_LOAN_FIELDS:
            if field in data and data.get(field) is not None:
                if loan.get(field) != data.get(field):
                    loan.set(field, data.get(field))
                    has_changes = True

        if "collaterals" in data and data.get("collaterals"):
            if not loan.is_secured_loan:
                loan.is_secured_loan = 1
                has_changes = True

        if "loan_charges" in data:
            if sync_loan_charges(loan, data.get("loan_charges")):
                has_changes = True

        if has_changes:
            loan.save(ignore_permissions=True)

        if "collaterals" in data:
            sync_loan_security_assignment(loan, data.get("collaterals"))

        return get_loan_by_id(loan.name)

    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        raise e


# def get_loan_by_id(loan_id: str) -> Dict[str, Any]:
#     if not frappe.db.exists("Loan", loan_id):
#         raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

#     doc = frappe.get_doc("Loan", loan_id)
#     result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

#     charges = []
#     for row in doc.get("loan_charges", []):
#         charges.append(
#             {
#                 "name": row.name,
#                 "charge": row.charge,
#                 "amount": row.amount,
#                 "account": row.account,
#                 "treatment_of_charge": row.treatment_of_charge,
#             }
#         )
#     result["loan_charges"] = charges

#     assignments = frappe.get_all(
#         "Loan Security Assignment",
#         filters={"loan": loan_id, "docstatus": ["<", 2]},
#         fields=[
#             "name",
#             "status",
#             "total_security_value",
#             "maximum_loan_value",
#             "reference_no",
#             "description",
#         ],
#     )
#     if assignments:
#         assignment_info = assignments[0]
#         assignment_doc = frappe.get_doc(
#             "Loan Security Assignment", assignment_info.name
#         )

#         items = []
#         for row in assignment_doc.get("securities"):
#             items.append(
#                 {
#                     "loan_security": row.get("loan_security"),
#                     "qty": row.get("qty"),
#                     "loan_security_price": row.get("loan_security_price"),
#                     "amount": row.get("amount", 0),
#                 }
#             )

#         assignment_info["items"] = items
#         result["collaterals"] = assignment_info
#     else:
#         result["collaterals"] = None

#     return result

def get_loan_by_id(loan_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    doc = frappe.get_doc("Loan", loan_id)
    result = {field: doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}
    result["loan_application_number"] = None
    custom_details = doc.get("custom_loan_details", [])
    if custom_details:
        result["loan_application_number"] = custom_details[0].get("loan_application_number")

    charges = []
    for row in doc.get("loan_charges", []):
        charges.append(
            {
                "name": row.name,
                "charge": row.charge,
                "amount": row.amount,
                "account": row.account,
                "treatment_of_charge": row.treatment_of_charge,
            }
        )
    result["loan_charges"] = charges

    assignments = frappe.get_all(
        "Loan Security Assignment",
        filters={"loan": loan_id, "docstatus": ["<", 2]},
        fields=[
            "name",
            "status",
            "total_security_value",
            "maximum_loan_value",
            "reference_no",
            "description",
        ],
    )
    if assignments:
        assignment_info = assignments[0]
        assignment_doc = frappe.get_doc(
            "Loan Security Assignment", assignment_info.name
        )

        items = []
        for row in assignment_doc.get("securities"):
            items.append(
                {
                    "loan_security": row.get("loan_security"),
                    "qty": row.get("qty"),
                    "loan_security_price": row.get("loan_security_price"),
                    "amount": row.get("amount", 0),
                }
            )

        assignment_info["items"] = items
        result["collaterals"] = assignment_info
    else:
        result["collaterals"] = None

    attached_files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Loan", "attached_to_name": loan_id},
        fields=["name", "file_name", "file_url", "is_private"]
    )
    result["attachments"] = attached_files

    return result

def get_loans(
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
            ["applicant", "like", search_term],
            ["applicant_name", "like", search_term],
        ]

    safe_filters = build_loan_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tabLoan`.`{sort_by}` {sort_order_clean}"

    loans = frappe.get_all(
        "Loan",
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    total_loans = len(
        frappe.get_all(
            "Loan",
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )
    total_pages = (total_loans + page_size - 1) // page_size

    return loans, total_loans, total_pages


def delete_loan(loan_id: str):
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    docstatus = frappe.db.get_value("Loan", loan_id, "docstatus")
    if docstatus == 1:
        raise frappe.ValidationError(
            f"Cannot delete a submitted Loan '{loan_id}'. Cancel it first."
        )

    frappe.delete_doc("Loan", loan_id, ignore_permissions=True)


def process_approval(loan_id: str):
    loan = frappe.get_doc("Loan", loan_id)

    if loan.docstatus == 1:
        raise frappe.ValidationError("Loan is already approved.")
    if loan.docstatus == 2:
        raise frappe.ValidationError(
            "Cannot approve a cancelled Loan. Please amend it first."
        )

    assignments = frappe.get_all(
        "Loan Security Assignment", filters={"loan": loan_id, "docstatus": 0}
    )
    for a in assignments:
        assignment_doc = frappe.get_doc("Loan Security Assignment", a.name)
        assignment_doc.submit()

    fresh_loan = frappe.get_doc("Loan", loan_id)

    secured_assignments = frappe.get_all(
        "Loan Security Assignment",
        filters={"loan": loan_id, "docstatus": 1},
        fields=["total_security_value", "maximum_loan_value"],
    )

    if secured_assignments:
        total_sec = sum(
            [frappe.utils.flt(x.total_security_value) for x in secured_assignments]
        )

        fresh_loan.is_secured_loan = 1
        if total_sec > 0:
            fresh_loan.total_security_value = total_sec

        fresh_loan.save(ignore_permissions=True)

    fresh_loan.submit()

    return {
        "id": fresh_loan.name,
        "status": fresh_loan.status,
        "docstatus": fresh_loan.docstatus,
    }


def process_cancellation(loan_id: str):
    loan = frappe.get_doc("Loan", loan_id)

    if loan.docstatus == 2:
        raise frappe.ValidationError("Loan is already cancelled.")
    if loan.docstatus == 0:
        raise frappe.ValidationError("Cannot cancel a Draft Loan. Submit it first.")

    loan.cancel()

    assignments = frappe.get_all(
        "Loan Security Assignment", filters={"loan": loan_id, "docstatus": 1}
    )
    for a in assignments:
        assignment_doc = frappe.get_doc("Loan Security Assignment", a.name)
        assignment_doc.cancel()

    return {"id": loan.name, "status": loan.status, "docstatus": loan.docstatus}


def process_amendment(loan_id: str):
    loan = frappe.get_doc("Loan", loan_id)

    if loan.docstatus == 0:
        raise frappe.ValidationError("Loan is already in Draft state.")
    if loan.docstatus == 1:
        raise frappe.ValidationError("Cannot amend an approved Loan. Cancel it first.")

    amended_doc = frappe.copy_doc(loan)
    amended_doc.amended_from = loan.name
    amended_doc.docstatus = 0
    amended_doc.insert()

    return {
        "id": amended_doc.name,
        "status": amended_doc.status,
        "docstatus": amended_doc.docstatus,
        "amended_from": amended_doc.amended_from,
    }


def update_loan_status(loan_id: str, action: str):
    if action == "approved":
        return process_approval(loan_id)
    elif action == "cancelled":
        return process_cancellation(loan_id)
    elif action == "amend":
        return process_amendment(loan_id)
    else:
        raise frappe.ValidationError(
            "Invalid action. Allowed: approved, cancelled, amend"
        )


def get_repayment_schedule_by_id(loan_id: str) -> Dict[str, Any]:
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    schedule_doc_name = frappe.db.get_value(
        "Loan Repayment Schedule",
        {"loan": loan_id, "docstatus": 1},
        "name",
        order_by="creation desc",
    )

    if not schedule_doc_name:
        return {"id": loan_id, "maturity_date": None, "repayment_schedule": []}

    schedule_doc = frappe.get_doc("Loan Repayment Schedule", schedule_doc_name)

    schedule = []
    for row in schedule_doc.get("repayment_schedule") or []:
        schedule.append(
            {
                "no": row.idx,
                "name": row.name,
                "payment_date": row.payment_date,
                "number_of_days": row.number_of_days,
                "principal_amount": row.principal_amount,
                "interest_amount": row.interest_amount,
                "total_payment": row.total_payment,
                "balance_loan_amount": row.balance_loan_amount,
                "charges": row.charges,
                "demand_generated": row.demand_generated,
            }
        )

    return {
        "id": loan_id,
        "maturity_date": schedule_doc.get("maturity_date"),
        "repayment_schedule": schedule,
    }
