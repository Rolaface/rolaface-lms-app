"""
Investor Flow maturity: the investor's choice on the maturity date.

Redeem : pay every unpaid schedule row (principal + interest) from the Company Bank -> Status Matured.
Renew  : pay the interest still owed in cash; carry the unpaid principal (whole rupees; any paise are
         paid out) into a new Draft investment for the same investor -> old Status Renewed.
         The new investment goes through Approve -> Contract -> Receive as usual; its Receive posts no
         bank entry because the money never left Investor Deposits.
"""
import math
import frappe
from typing import Dict, Any, Tuple
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from .constant import (
    DOCTYPE,
    SCHEDULE_TABLE_FIELD,
    STATUS_RECEIVED,
    STATUS_MATURED,
    STATUS_RENEWED,
    ROW_STATUS_PAID,
)
from .utils import _as_list
from . import accounting, service

MATURITY_VIEWS = ["due", "upcoming", "closed"]

RETURN_FIELDS_MATURITY_LIST = [
    "name", "investor", "investment_product", "amount_invested", "rate_of_interest",
    "frequency", "mat_date", "status", "renewed_to", "renewed_from",
]


def _outstanding(rows) -> Dict[str, Any]:
    """What is still owed on the unpaid schedule rows."""
    unpaid = [r for r in rows if r.get("status") != ROW_STATUS_PAID]
    return {
        "rows_total": len(rows),
        "rows_paid": len(rows) - len(unpaid),
        "outstanding_principal": flt(sum(flt(r.get("principal_amount")) for r in unpaid), 2),
        "outstanding_interest": flt(
            sum(flt(r.get("interest_amount")) + flt(r.get("penalty_amount")) for r in unpaid), 2
        ),
    }


def get_investor_maturities(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """due: Received and maturity date reached; upcoming: Received, not yet due; closed: Matured / Renewed."""
    view = args.get("view") or "due"
    if view not in MATURITY_VIEWS:
        raise frappe.ValidationError(f"Invalid view. Allowed: {', '.join(MATURITY_VIEWS)}")

    today = getdate(nowdate())
    # An empty Maturity Date would count as already due, so only rows that have one are listed.
    if view == "due":
        filters = [["status", "=", STATUS_RECEIVED], ["mat_date", "is", "set"], ["mat_date", "<=", today]]
        order_by = "mat_date asc"
    elif view == "upcoming":
        filters = [["status", "=", STATUS_RECEIVED], ["mat_date", "is", "set"], ["mat_date", ">", today]]
        order_by = "mat_date asc"
    else:
        filters = [["status", "in", [STATUS_MATURED, STATUS_RENEWED]]]
        order_by = "modified desc"

    if args.get("investment_product"):
        filters.append(["investment_product", "in", _as_list(args.get("investment_product"))])

    or_filters = None
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        investor_ids = frappe.get_all("Customer", filters={"customer_name": ["like", search_term]}, pluck="name")
        or_filters = [["name", "like", search_term], ["investor", "like", search_term]]
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    rows = frappe.get_all(
        DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=RETURN_FIELDS_MATURITY_LIST,
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        order_by=order_by,
    )
    total_records = len(frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name"))
    total_pages = (total_records + page_size - 1) // page_size

    schedule_by_flow: Dict[str, list] = {}
    if rows:
        for r in frappe.get_all(
            "Custom Investor Earning Schedule",
            filters={"parenttype": DOCTYPE, "parent": ["in", [row.name for row in rows]]},
            fields=["parent", "status", "principal_amount", "interest_amount", "penalty_amount"],
        ):
            schedule_by_flow.setdefault(r.parent, []).append(r)

    investor_names = service._get_names("Customer", "customer_name", [r.investor for r in rows])
    product_names = service._get_names(
        "Custom Investment Product", "product_name", [r.investment_product for r in rows]
    )
    for row in rows:
        row["investor_id"] = row.investor
        row["investor"] = investor_names.get(row.investor) or row.investor
        row["investment_product_name"] = product_names.get(row.investment_product) or row.investment_product
        row["is_due"] = bool(row.mat_date) and getdate(row.mat_date) <= today
        row.update(_outstanding(schedule_by_flow.get(row.name, [])))

    return rows, total_records, total_pages


def _renewal_defaults(doc) -> Dict[str, Any]:
    """New terms pre-filled from the old investment: same product, rate and frequency; same tenure."""
    mat_date = getdate(doc.mat_date)
    start = getdate(doc.payment_date or doc.first_repay_date or doc.mat_date)
    tenure_days = max((mat_date - start).days, 1)

    unit, step = service.SCHEDULE_FREQUENCY_STEP.get(doc.frequency or "Monthly", ("months", 1))
    first_repayment = add_months(mat_date, step) if unit == "months" else add_days(mat_date, step)

    return {
        "investment_product": doc.investment_product,
        "interest_rate": flt(doc.rate_of_interest),
        "repayment_frequency": doc.frequency,
        "penalty_rate": flt(doc.rate_of_penalty),
        "first_repayment_date": str(getdate(first_repayment)),
        "maturity_date": str(getdate(add_days(mat_date, tenure_days))),
    }


def get_investor_maturity_by_id(investor_flow_id: str) -> Dict[str, Any]:
    doc = service._get_earning_doc(investor_flow_id)
    rows = doc.get(SCHEDULE_TABLE_FIELD) or []
    outstanding = _outstanding(rows)
    carry = math.floor(outstanding["outstanding_principal"])

    return {
        "id": doc.name,
        "status": doc.status,
        "investor_id": doc.investor,
        "investor": frappe.db.get_value("Customer", doc.investor, "customer_name") or doc.investor,
        "investment_product": doc.investment_product,
        "investment_product_name": frappe.db.get_value(
            "Custom Investment Product", doc.investment_product, "product_name"
        ) or doc.investment_product,
        "amount_invested": doc.amount_invested,
        "rate_of_interest": doc.rate_of_interest,
        "frequency": doc.frequency,
        "payment_date": doc.payment_date,
        "mat_date": doc.mat_date,
        "is_due": bool(doc.mat_date) and getdate(doc.mat_date) <= getdate(nowdate()),
        "renewed_to": doc.get("renewed_to"),
        "renewed_from": doc.get("renewed_from"),
        **outstanding,
        # Renew: whole rupees carried into the new investment; the paise are paid out.
        "renewal_carry_amount": carry,
        "renewal_cash_payout": flt(outstanding["outstanding_principal"] - carry + outstanding["outstanding_interest"], 2),
        "renewal_defaults": _renewal_defaults(doc) if doc.mat_date else None,
    }


def _get_due_doc(investor_flow_id: str):
    doc = service._get_earning_doc(investor_flow_id, for_update=True)
    if not doc.mat_date or getdate(doc.mat_date) > getdate(nowdate()):
        raise frappe.ValidationError(
            f"Investor Flow '{doc.name}' matures on {doc.mat_date}; it can be redeemed or renewed from that date."
        )
    return doc


def redeem_investor_flow(investor_flow_id: str) -> Dict[str, Any]:
    """Pays every unpaid schedule row (dated today) and sets Status Matured."""
    doc = _get_due_doc(investor_flow_id)
    settings = accounting.get_accounting_settings()
    today = getdate(nowdate())

    for row in sorted(doc.get(SCHEDULE_TABLE_FIELD) or [], key=lambda r: r.idx):
        if row.status != ROW_STATUS_PAID:
            accounting.pay_row(doc, row, settings, today, f"Redemption of {doc.name}")

    doc.status = STATUS_MATURED
    doc.save(ignore_permissions=True)
    return get_investor_maturity_by_id(doc.name)


def renew_investor_flow(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Pays the interest still owed, carries the unpaid principal into a new Draft investment."""
    doc = _get_due_doc(investor_flow_id)
    rows = sorted(doc.get(SCHEDULE_TABLE_FIELD) or [], key=lambda r: r.idx)
    unpaid = [r for r in rows if r.status != ROW_STATUS_PAID]
    outstanding_principal = flt(sum(flt(r.principal_amount) for r in unpaid), 2)
    carry = math.floor(outstanding_principal)
    if carry <= 0:
        raise frappe.ValidationError("No principal is left to renew. Use Redeem to close this investment.")

    required = ["investment_product", "interest_rate", "repayment_frequency", "first_repayment_date", "maturity_date"]
    missing = [f for f in required if data.get(f) in (None, "")]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    new_flow = service.create_investor_flow({
        "investor": doc.investor,
        "investment_product": data.get("investment_product"),
        "investment_amount": carry,
        "repayment_frequency": data.get("repayment_frequency"),
        "maturity_date": data.get("maturity_date"),
        "interest_rate": data.get("interest_rate"),
        "first_repayment_date": data.get("first_repayment_date"),
        "penalty_rate": data.get("penalty_rate"),
    })
    frappe.db.set_value(DOCTYPE, new_flow["name"], "renewed_from", doc.name)

    # Interest (and the paise of principal) are paid in cash; the whole-rupee principal stays invested.
    settings = accounting.get_accounting_settings()
    today = getdate(nowdate())
    paise = flt(outstanding_principal - carry, 2)
    for row in unpaid:
        to_pay = min(paise, flt(row.principal_amount, 2))
        paise = flt(paise - to_pay, 2)
        accounting.pay_row(doc, row, settings, today, f"Renewal of {doc.name}", principal_to_pay=to_pay)

    doc.status = STATUS_RENEWED
    doc.renewed_to = new_flow["name"]
    doc.save(ignore_permissions=True)
    return get_investor_maturity_by_id(doc.name)
