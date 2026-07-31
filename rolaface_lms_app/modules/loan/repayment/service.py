import frappe
from typing import Tuple, Dict,List, Any
from .constant import ALLOWED_PAYMENT_FIELD

def create_payment(data: Dict[str, Any]):
    payment_doc = frappe.new_doc("Loan Repayment")
    for field in ALLOWED_PAYMENT_FIELD:
        if field in data and data.get(field) is not None:
            payment_doc.set(field, data.get(field))
    payment_doc.insert(ignore_permissions=True)


def get_loan_repayment_account(search_term: str = "", limit: int = 20) -> List[Dict[str, Any]]:

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

    loan_meta = frappe.get_meta("Loan")

    if loan_meta.has_field("applicant_name"):
        or_filters.append(["Loan", "applicant_name", "like", like_term])

    if phone_matched_applicants:
        or_filters.append(["Loan", "applicant", "in", phone_matched_applicants])

    fields = [
        "name as against_loan",
        "applicant",
        "applicant_type",
        "sanctioned_amount",
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

    loans = frappe.get_list(
        "Loan",
        or_filters=or_filters,
        fields=fields,
        limit_page_length=limit,
        order_by="modified desc",
    )

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