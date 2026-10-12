"""
Investor payouts: money paid by the company to the investor against the repayment schedule (EMIs).

A payout is a row of Custom Investor Payouts (table "payouts" on Custom Investor Flow):
  Draft -> Approved (Journal Entry posted, EMIs paid) -> Cancelled (Journal Entry cancelled, EMIs restored).
  Draft can be edited / deleted; Approved can only be cancelled (the latest one first); Cancelled can be deleted.

Payment Type:
  Pay Dues - the next unpaid EMI (what is still owed on it).
  Pay Full - every unpaid EMI.
  Pay Any  - any amount up to what is owed; applied to the oldest unpaid EMI first, and within an EMI
             interest, then penalty, then principal. An EMI only partly covered becomes "Partially Paid".

Each EMI keeps how much of it has been paid (paid_amount on Custom Investor Earning Schedule).

Journal Entry on Approve (posting date = value date, party = investor):
  Dr Investor Creditor   (principal paid)
  Dr Interest Payable    (interest / penalty already booked by the accrual)
  Dr Penalty Expense     (penalty added after the accrual, not yet booked)
  Cr Paid From           (the company bank GL chosen on the payout)
Every EMI touched that is still Pending is first accrued (booked on its due date, or on the value date
when it is paid before it is due), exactly like a single EMI payout.
"""
import json
import frappe
from typing import Dict, Any, List, Optional, Tuple
from frappe.utils import flt, getdate, nowdate

from .constant import (
    DOCTYPE,
    EARNING_FUND_STATUSES,
    ROW_STATUS_PENDING,
    ROW_STATUS_ACCRUED,
    ROW_STATUS_PAID,
)
from .utils import _as_list, _parse_date, current_schedule, schedule_version
from . import accounting, service

PAYOUT_TABLE_FIELD = "payouts"
PAYOUT_DOCTYPE = "Custom Investor Payouts"
ROW_STATUS_PARTIALLY_PAID = "Partially Paid"

PAY_DUES = "Pay Dues"
PAY_ANY = "Pay Any"
PAY_FULL = "Pay Full"
PAYMENT_TYPES = [PAY_DUES, PAY_ANY, PAY_FULL]
PAYMENT_MODES = ["Wire Transfer", "Cheque", "Cash", "Bank Draft"]

PAYOUT_DRAFT = "Draft"
PAYOUT_APPROVED = "Approved"
PAYOUT_CANCELLED = "Cancelled"

INPUT_FIELDS = [
    "value_date", "payment_type", "payment_amount", "payment_mode", "paid_from", "investor_bank_account",
    "reference_number", "reference_date", "comment",
]
PAYOUT_FIELDS = INPUT_FIELDS + [
    "record_status", "journal_entry", "principal_paid", "interest_paid", "penalty_paid", "schedule_rows",
]


# ------------------------------- EMI figures -------------------------------

def _paid(row) -> float:
    return flt(row.get("paid_amount"), 2)


def _row_parts(row) -> Dict[str, float]:
    """What is still owed on an EMI, split interest / penalty / principal (paid in that order)."""
    interest, penalty, principal = flt(row.interest_amount, 2), flt(row.penalty_amount, 2), flt(row.principal_amount, 2)
    paid = _paid(row)
    paid_interest = min(paid, interest)
    paid_penalty = min(max(paid - interest, 0), penalty)
    paid_principal = max(paid - interest - penalty, 0)
    return {
        "interest": flt(interest - paid_interest, 2),
        "penalty": flt(penalty - paid_penalty, 2),
        "principal": flt(principal - paid_principal, 2),
    }


def _row_remaining(row) -> float:
    return flt(flt(row.total_payment, 2) - _paid(row), 2)


def _unpaid_rows(doc) -> list:
    """Unpaid / partly paid EMIs of the current schedule, oldest first."""
    rows = [r for r in current_schedule(doc) if r.status != ROW_STATUS_PAID and _row_remaining(r) > 0]
    return sorted(rows, key=lambda r: (getdate(r.payment_date), r.idx))


def _allocate(rows: list, amount: float) -> List[Dict[str, Any]]:
    """Applies amount to the EMIs oldest first; within an EMI interest, then penalty, then principal."""
    left = flt(amount, 2)
    allocations = []
    for row in rows:
        if left <= 0:
            break
        parts = _row_parts(row)
        piece = {"row": row.name, "payment_date": str(getdate(row.payment_date)), "interest": 0.0, "penalty": 0.0, "principal": 0.0}
        for key in ("interest", "penalty", "principal"):
            take = flt(min(left, parts[key]), 2)
            piece[key] = take
            left = flt(left - take, 2)
        piece["amount"] = flt(piece["interest"] + piece["penalty"] + piece["principal"], 2)
        if piece["amount"] > 0:
            piece["settles"] = flt(_row_remaining(row) - piece["amount"], 2) <= 0
            allocations.append(piece)
    return allocations


def _amount_for(doc, payment_type: str, amount=None) -> float:
    rows = _unpaid_rows(doc)
    if not rows:
        raise frappe.ValidationError("Nothing is owed on this investment: every EMI is paid.")
    owed = flt(sum(_row_remaining(r) for r in rows), 2)
    if payment_type == PAY_DUES:
        return _row_remaining(rows[0])
    if payment_type == PAY_FULL:
        return owed
    value = flt(amount, 2)
    if value <= 0:
        raise frappe.ValidationError("Payment Amount must be more than 0.")
    if value > owed:
        raise frappe.ValidationError(f"Payment Amount cannot be more than what is owed ({owed:,.2f}).")
    return value


def _number_of(doc, row_name: str) -> Optional[int]:
    for i, r in enumerate(current_schedule(doc), start=1):
        if r.name == row_name:
            return i
    return None


# ---------------------------------- Read ----------------------------------

def _get_doc(investor_flow_id: str):
    if not investor_flow_id or not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")
    return frappe.get_doc(DOCTYPE, investor_flow_id)


def _get_payout(doc, payout_name: str):
    row = next((p for p in doc.get(PAYOUT_TABLE_FIELD) or [] if p.name == payout_name), None)
    if not row:
        raise frappe.DoesNotExistError(f"Payout '{payout_name}' is not on Investor Flow '{doc.name}'.")
    return row


def _payout_dict(doc, p) -> Dict[str, Any]:
    result = {f: p.get(f) for f in PAYOUT_FIELDS}
    for f in ("value_date", "reference_date"):
        result[f] = str(result[f]) if result[f] else None
    result["record_status"] = p.get("record_status") or PAYOUT_DRAFT
    result.update({"name": p.name, "idx": p.idx, "investment_id": doc.name})
    try:
        result["allocations"] = json.loads(p.get("schedule_rows") or "[]")
    except ValueError:
        result["allocations"] = []
    return result


def _schedule_rows(doc) -> List[Dict[str, Any]]:
    rows = []
    for i, r in enumerate(current_schedule(doc), start=1):
        parts = _row_parts(r)
        rows.append({
            "name": r.name,
            "number": i,
            "payment_date": str(getdate(r.payment_date)),
            "principal": flt(r.principal_amount, 2),
            "interest": flt(r.interest_amount, 2),
            "penalty": flt(r.penalty_amount, 2),
            "total": flt(r.total_payment, 2),
            "paid": _paid(r) if r.status != ROW_STATUS_PAID else flt(r.total_payment, 2),
            "remaining": 0 if r.status == ROW_STATUS_PAID else _row_remaining(r),
            "remaining_parts": parts if r.status != ROW_STATUS_PAID else {"interest": 0, "penalty": 0, "principal": 0},
            "status": r.status or ROW_STATUS_PENDING,
            "payout_entry": r.payout_entry,
        })
    return rows


def get_payout_context(investor_flow_id: str) -> Dict[str, Any]:
    """Everything the payout screen needs for one investment."""
    doc = _get_doc(investor_flow_id)
    unpaid = _unpaid_rows(doc)
    next_row = unpaid[0] if unpaid else None
    settings_bank = frappe.db.get_single_value("Custom Investor Settings", "company_bank_account")
    customer = frappe.db.get_value("Customer", doc.investor, ["customer_name", "email_id", "mobile_no"], as_dict=True) or {}
    return {
        "id": doc.name,
        "investor_id": doc.investor,
        "investor": customer.get("customer_name") or doc.investor,
        "investor_email": customer.get("email_id"),
        "investor_mobile": customer.get("mobile_no"),
        "investment_product": doc.investment_product,
        "investment_product_name": frappe.db.get_value("Custom Investment Product", doc.investment_product, "product_name")
        or doc.investment_product,
        "investment_amount": flt(doc.investment_amount),
        "default_paid_from": settings_bank,
        "bank_accounts": service.get_investor_bank_accounts(doc.investor),
        "next_emi": {
            "name": next_row.name,
            "number": _number_of(doc, next_row.name),
            "payment_date": str(getdate(next_row.payment_date)),
            **_row_parts(next_row),
            "total": _row_remaining(next_row),
            "status": next_row.status,
        } if next_row else None,
        "outstanding": {
            "emis": len(unpaid),
            **{k: flt(sum(_row_parts(r)[k] for r in unpaid), 2) for k in ("interest", "penalty", "principal")},
            "total": flt(sum(_row_remaining(r) for r in unpaid), 2),
        },
        "schedule": _schedule_rows(doc),
        "payouts": [_payout_dict(doc, p) for p in doc.get(PAYOUT_TABLE_FIELD) or []],
    }


def preview_payout(investor_flow_id: str, payment_type: str, amount=None) -> Dict[str, Any]:
    """The amount and how it is split over the EMIs (the Payment Effect); nothing is saved."""
    if payment_type not in PAYMENT_TYPES:
        raise frappe.ValidationError(f"Payment Type must be one of: {', '.join(PAYMENT_TYPES)}.")
    doc = _get_doc(investor_flow_id)
    value = _amount_for(doc, payment_type, amount)
    allocations = _allocate(_unpaid_rows(doc), value)
    for a in allocations:
        a["number"] = _number_of(doc, a["row"])
    return {
        "payment_amount": value,
        "principal": flt(sum(a["principal"] for a in allocations), 2),
        "interest": flt(sum(a["interest"] for a in allocations), 2),
        "penalty": flt(sum(a["penalty"] for a in allocations), 2),
        "allocations": allocations,
    }


def get_payout_candidates(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Investments with EMIs still unpaid, found by investment ID or investor name / mobile / ID / email."""
    filters = {"fund_status": ["in", EARNING_FUND_STATUSES], "status": ["!=", "Cancelled"]}
    or_filters = None
    if search:
        term = f"%{str(search).strip()}%"
        or_filters = [["name", "like", term], ["investor", "like", term]]
        investor_ids = service._matching_investors(term)
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])
    names = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name", order_by="modified desc", limit=30)

    result = []
    for name in names:
        doc = frappe.get_doc(DOCTYPE, name)
        unpaid = _unpaid_rows(doc)
        if not unpaid:
            continue
        customer = frappe.db.get_value("Customer", doc.investor, ["customer_name", "email_id", "mobile_no"], as_dict=True) or {}
        result.append({
            "id": doc.name,
            "investor_id": doc.investor,
            "investor": customer.get("customer_name") or doc.investor,
            "investor_email": customer.get("email_id"),
            "investor_mobile": customer.get("mobile_no"),
            "next_emi_date": str(getdate(unpaid[0].payment_date)),
            "next_emi_amount": _row_remaining(unpaid[0]),
            "outstanding": flt(sum(_row_remaining(r) for r in unpaid), 2),
        })
    return result


def get_payouts(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Every payout (all investments), newest first."""
    filters = {}
    if args.get("record_status"):
        filters["record_status"] = ["in", _as_list(args.get("record_status"))]
    if args.get("payment_type"):
        filters["payment_type"] = ["in", _as_list(args.get("payment_type"))]
    search = args.get("search")
    if search:
        term = f"%{str(search).strip()}%"
        investor_ids = service._matching_investors(term)
        parents = frappe.get_all(
            DOCTYPE,
            or_filters=[["name", "like", term]] + ([["investor", "in", investor_ids]] if investor_ids else []),
            pluck="name",
        )
        filters["parent"] = ["in", parents or [""]]

    query = dict(filters={**filters, "parenttype": DOCTYPE, "parentfield": PAYOUT_TABLE_FIELD}, parent_doctype=DOCTYPE)
    rows = frappe.get_all(
        PAYOUT_DOCTYPE,
        fields=["name", "parent", "idx", "creation"] + PAYOUT_FIELDS,
        order_by="creation desc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        **query,
    )
    total = len(frappe.get_all(PAYOUT_DOCTYPE, pluck="name", **query))

    investors = dict(frappe.get_all(
        DOCTYPE, filters={"name": ["in", list({r.parent for r in rows})]}, fields=["name", "investor"], as_list=True,
    )) if rows else {}
    names = service._get_names("Customer", "customer_name", list(investors.values()))
    for r in rows:
        r["investment_id"] = r.parent
        r["investor_id"] = investors.get(r.parent)
        r["investor"] = names.get(investors.get(r.parent)) or investors.get(r.parent)
        r["record_status"] = r.get("record_status") or PAYOUT_DRAFT
        for f in ("value_date", "reference_date"):
            r[f] = str(r[f]) if r.get(f) else None
    return rows, total, (total + page_size - 1) // page_size


# ---------------------------------- Write ----------------------------------

def _validated(doc, data: Dict[str, Any]) -> Dict[str, Any]:
    if (doc.fund_status or "") not in EARNING_FUND_STATUSES or doc.status == "Cancelled":
        raise frappe.ValidationError("Payouts can be recorded only for an investment with a repayment schedule.")

    payment_type = data.get("payment_type")
    if payment_type not in PAYMENT_TYPES:
        raise frappe.ValidationError(f"Payment Type must be one of: {', '.join(PAYMENT_TYPES)}.")
    if data.get("payment_mode") not in PAYMENT_MODES:
        raise frappe.ValidationError(f"Payment Mode must be one of: {', '.join(PAYMENT_MODES)}.")

    missing = [label for f, label in (
        ("value_date", "Value Date"), ("paid_from", "Paid From"), ("reference_number", "Reference Number"),
        ("reference_date", "Reference Date"),
    ) if not data.get(f)]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")
    value_date = _parse_date(data.get("value_date"), "Value Date")
    reference_date = _parse_date(data.get("reference_date"), "Reference Date")

    account = frappe.db.get_value("Account", data.get("paid_from"), ["is_group", "disabled"], as_dict=True)
    if not account:
        raise frappe.DoesNotExistError(f"Account '{data.get('paid_from')}' does not exist.")
    if account.is_group or account.disabled:
        raise frappe.ValidationError(f"Paid From '{data.get('paid_from')}' must be an enabled ledger (not a group) account.")

    bank_account = data.get("investor_bank_account")
    if bank_account:
        party = frappe.db.get_value("Bank Account", bank_account, ["party_type", "party"], as_dict=True)
        if not party:
            raise frappe.DoesNotExistError(f"Bank Account '{bank_account}' does not exist.")
        if party.party_type != "Customer" or party.party != doc.investor:
            raise frappe.ValidationError(f"Bank Account '{bank_account}' does not belong to this investor.")

    amount = _amount_for(doc, payment_type, data.get("payment_amount"))
    return {
        "value_date": value_date,
        "payment_type": payment_type,
        "payment_amount": amount,
        "payment_mode": data.get("payment_mode"),
        "paid_from": data.get("paid_from"),
        "investor_bank_account": bank_account or None,
        "reference_number": str(data.get("reference_number")).strip(),
        "reference_date": reference_date,
        "comment": data.get("comment"),
    }


def add_payout(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    doc = _get_doc(investor_flow_id)
    values = _validated(doc, data)
    row = doc.append(PAYOUT_TABLE_FIELD, {**values, "record_status": PAYOUT_DRAFT})
    doc.save(ignore_permissions=True)
    return _payout_dict(doc, row)


def update_payout(investor_flow_id: str, payout_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    doc = _get_doc(investor_flow_id)
    row = _get_payout(doc, payout_name)
    if (row.get("record_status") or PAYOUT_DRAFT) != PAYOUT_DRAFT:
        raise frappe.ValidationError("Only a Draft payout can be edited.")
    for field, value in _validated(doc, data).items():
        row.set(field, value)
    doc.save(ignore_permissions=True)
    return _payout_dict(doc, row)


def delete_payout(investor_flow_id: str, payout_name: str):
    doc = _get_doc(investor_flow_id)
    row = _get_payout(doc, payout_name)
    if (row.get("record_status") or PAYOUT_DRAFT) not in (PAYOUT_DRAFT, PAYOUT_CANCELLED):
        raise frappe.ValidationError("Only a Draft or Cancelled payout can be deleted.")
    doc.remove(row)
    doc.save(ignore_permissions=True)


def approve_payout(investor_flow_id: str, payout_name: str) -> Dict[str, Any]:
    doc = _get_doc(investor_flow_id)
    payout = _get_payout(doc, payout_name)
    if (payout.get("record_status") or PAYOUT_DRAFT) != PAYOUT_DRAFT:
        raise frappe.ValidationError("Only a Draft payout can be approved.")

    # Re-checked with today's figures (an earlier payout may have paid part of it since it was saved).
    values = _validated(doc, {f: payout.get(f) for f in INPUT_FIELDS})
    if values["payment_type"] == PAY_ANY and flt(values["payment_amount"], 2) != flt(payout.payment_amount, 2):
        raise frappe.ValidationError("The payout amount has changed; open the payout and save it again.")
    value_date = getdate(values["value_date"])
    rows_by_name = {r.name: r for r in current_schedule(doc)}
    allocations = _allocate(_unpaid_rows(doc), values["payment_amount"])
    if not allocations:
        raise frappe.ValidationError("Nothing is owed on this investment.")

    settings = accounting.get_accounting_settings()
    principal_total = interest_payable = penalty_expense = 0.0
    for a in allocations:
        row = rows_by_name[a["row"]]
        # Book the EMI's interest first (on its due date, or the value date when paid before it).
        if row.status in (None, "", ROW_STATUS_PENDING):
            accounting.accrue_row(doc, row, settings, min(getdate(row.payment_date), value_date))
            a["accrued_now"] = True
        accrued = accounting._accrued_amount(row, settings)
        booked_paid_before = min(_paid(row), flt(row.interest_amount) + flt(row.penalty_amount))
        booked_left = max(flt(accrued - booked_paid_before, 2), 0)
        interest_part = flt(a["interest"] + a["penalty"], 2)
        from_payable = min(interest_part, booked_left)
        interest_payable += from_payable
        penalty_expense += flt(interest_part - from_payable, 2)
        principal_total += a["principal"]
        a["number"] = _number_of(doc, a["row"])

    entry = accounting._make_journal_entry(
        {**settings, "company": frappe.db.get_value("Account", values["paid_from"], "company") or settings["company"]},
        doc.investor,
        value_date,
        f"Payout ({values['payment_type']}) for Investor Flow {doc.name}",
        [
            {"account": settings["investor_creditor_account"], "debit": flt(principal_total, 2)},
            {"account": settings["interest_payable_account"], "debit": flt(interest_payable, 2)},
            {"account": settings["penalty_expense_account"], "debit": flt(penalty_expense, 2)},
            {"account": values["paid_from"], "credit": flt(values["payment_amount"], 2)},
        ],
        reference_no=values["reference_number"],
    )

    for a in allocations:
        row = rows_by_name[a["row"]]
        row.paid_amount = flt(_paid(row) + a["amount"], 2)
        row.status = ROW_STATUS_PAID if _row_remaining(row) <= 0 else ROW_STATUS_PARTIALLY_PAID
        row.payout_entry = entry

    payout.record_status = PAYOUT_APPROVED
    payout.payment_amount = values["payment_amount"]
    payout.journal_entry = entry
    payout.principal_paid = flt(sum(a["principal"] for a in allocations), 2)
    payout.interest_paid = flt(sum(a["interest"] for a in allocations), 2)
    payout.penalty_paid = flt(sum(a["penalty"] for a in allocations), 2)
    payout.schedule_rows = json.dumps(allocations)

    from .renewal import refresh_payment_status
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return _payout_dict(doc, payout)


def cancel_payout(investor_flow_id: str, payout_name: str) -> Dict[str, Any]:
    doc = _get_doc(investor_flow_id)
    payout = _get_payout(doc, payout_name)
    if payout.get("record_status") != PAYOUT_APPROVED:
        raise frappe.ValidationError("Only an Approved payout can be cancelled.")

    # Cancelled latest first, so each EMI goes back exactly to what it was before.
    def approved_at(p):
        return frappe.db.get_value("Journal Entry", p.journal_entry, "creation") if p.journal_entry else None

    mine = approved_at(payout)
    later = [
        p for p in doc.get(PAYOUT_TABLE_FIELD) or []
        if p.get("record_status") == PAYOUT_APPROVED and p.name != payout.name
        and mine and (approved_at(p) or mine) > mine
    ]
    if later:
        raise frappe.ValidationError("A later approved payout exists on this investment; cancel that one first.")

    allocations = json.loads(payout.get("schedule_rows") or "[]")
    rows_by_name = {r.name: r for r in current_schedule(doc)}
    missing = [a["row"] for a in allocations if a["row"] not in rows_by_name]
    if missing:
        raise frappe.ValidationError(
            "The repayment schedule has changed since this payout was approved; it cannot be cancelled."
        )

    accounting.cancel_journal_entry(payout.journal_entry)
    for a in allocations:
        row = rows_by_name[a["row"]]
        row.paid_amount = max(flt(_paid(row) - flt(a["amount"]), 2), 0)
        if a.get("accrued_now") and row.accrual_entry and not row.paid_amount:
            # Booked by this payout only: undo the booking too.
            accounting.cancel_journal_entry(row.accrual_entry)
            row.accrual_entry = None
            row.status = ROW_STATUS_PENDING
        elif row.paid_amount:
            row.status = ROW_STATUS_PARTIALLY_PAID
        else:
            row.status = ROW_STATUS_ACCRUED if row.accrual_entry else ROW_STATUS_PENDING
        if row.payout_entry == payout.journal_entry:
            row.payout_entry = None

    payout.record_status = PAYOUT_CANCELLED
    from .renewal import refresh_payment_status
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return _payout_dict(doc, payout)
