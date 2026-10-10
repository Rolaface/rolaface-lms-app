"""
Investor 360: everything about one investor in one place.

- get_investor_portfolio : the investor, totals across their investments, and each investment.
- get_investment_detail  : one investment's contract terms, funds paid, repayment schedule and payouts.
- get_investor_statement : every fund paid in and every payout received, by date, with the principal balance.
- get_journal_entry_detail: a posted Journal Entry, line by line, with what each line means.

All money figures are calculated from the fund records (Custom Investor Record Fund) and the
current repayment schedule (Custom Investor Earning Schedule, highest version).
"""
import frappe
from typing import Dict, Any, List, Optional
from frappe.utils import flt, getdate

from .constant import (
    DOCTYPE,
    FUND_TABLE_FIELD,
    RECORD_STATUS_APPROVED,
    RECORD_STATUS_DRAFT,
    ROW_STATUS_PAID,
)
from .utils import current_schedule
from .constant import RENEWAL_ALL_FIELDS
from .renewal import _payment_status
from . import service

INVESTMENT_FIELDS = [
    "name", "investor", "investment_product", "status", "fund_status", "contract_status",
    "investment_amount", "interest_rate", "repayment_frequency", "first_repayment_date",
    "maturity_date", "penalty_rate", "creation",
]


def _payout_dates(entries: List[str]) -> Dict[str, Any]:
    """Posting date of each payout Journal Entry (the day the investor was actually paid)."""
    entries = [e for e in entries if e]
    if not entries:
        return {}
    return dict(frappe.get_all("Journal Entry", filters={"name": ["in", entries]},
                               fields=["name", "posting_date"], as_list=True))


def _investment_figures(doc) -> Dict[str, Any]:
    """What the investor paid in, what came back to them, and what is still owed."""
    funds = doc.get(FUND_TABLE_FIELD) or []
    approved = [r for r in funds if r.get("record_status") == RECORD_STATUS_APPROVED]
    drafts = [r for r in funds if (r.get("record_status") or RECORD_STATUS_DRAFT) == RECORD_STATUS_DRAFT]
    schedule = current_schedule(doc)
    paid_rows = [r for r in schedule if r.status == ROW_STATUS_PAID]
    open_rows = [r for r in schedule if r.status != ROW_STATUS_PAID]

    fund_paid_in = flt(sum(flt(r.amount_paid) for r in approved), 2)
    principal_returned = flt(sum(flt(r.principal_amount) for r in paid_rows), 2)
    interest_received = flt(sum(flt(r.interest_amount) + flt(r.penalty_amount) for r in paid_rows), 2)
    next_row = min(open_rows, key=lambda r: getdate(r.payment_date)) if open_rows else None

    return {
        "fund_paid_in": fund_paid_in,
        "fund_pending_approval": flt(sum(flt(r.amount_paid) for r in drafts), 2),
        "fund_remaining": max(flt(flt(doc.investment_amount) - fund_paid_in, 2), 0),
        "principal_returned": principal_returned,
        "interest_received": interest_received,
        "received_back": flt(principal_returned + interest_received, 2),
        "principal_outstanding": max(flt(fund_paid_in - principal_returned, 2), 0),
        "interest_outstanding": flt(sum(flt(r.interest_amount) + flt(r.penalty_amount) for r in open_rows), 2),
        "payouts_total": len(schedule),
        "payouts_done": len(paid_rows),
        "next_payout_date": next_row.payment_date if next_row else None,
        "next_payout_amount": flt(next_row.total_payment, 2) if next_row else 0,
    }


def _investor_info(investor: str) -> Dict[str, Any]:
    customer = frappe.db.get_value(
        "Customer", investor,
        ["name", "customer_name", "customer_type", "email_id", "mobile_no", "disabled"], as_dict=True,
    )
    if not customer:
        raise frappe.DoesNotExistError(f"Investor (Customer) '{investor}' does not exist.")
    return {
        "id": customer.name,
        "name": customer.customer_name or customer.name,
        "customer_type": customer.customer_type,
        "email": customer.email_id,
        "mobile": customer.mobile_no,
        "status": "Inactive" if customer.disabled else "Active",
    }


def get_investor_portfolio(investor: str) -> Dict[str, Any]:
    info = _investor_info(investor)
    names = frappe.get_all(DOCTYPE, filters={"investor": investor}, pluck="name", order_by="creation desc")
    product_names = service._get_names(
        "Custom Investment Product", "product_name",
        frappe.get_all(DOCTYPE, filters={"investor": investor}, pluck="investment_product"),
    )

    investments = []
    for name in names:
        doc = frappe.get_doc(DOCTYPE, name)
        investments.append({
            **{f: doc.get(f) for f in INVESTMENT_FIELDS},
            "investment_product_name": product_names.get(doc.investment_product) or doc.investment_product,
            **_investment_figures(doc),
        })

    def total(key):
        return flt(sum(flt(i[key]) for i in investments), 2)

    upcoming = [i for i in investments if i["next_payout_date"]]
    next_payout = min(upcoming, key=lambda i: getdate(i["next_payout_date"])) if upcoming else None

    return {
        "investor": info,
        "totals": {
            "investments": len(investments),
            "active": len([i for i in investments if i["status"] in ("Approved", "Paid")]),
            "contracted": total("investment_amount"),
            "fund_paid_in": total("fund_paid_in"),
            "fund_remaining": total("fund_remaining"),
            "received_back": total("received_back"),
            "principal_returned": total("principal_returned"),
            "interest_received": total("interest_received"),
            "principal_outstanding": total("principal_outstanding"),
            "interest_outstanding": total("interest_outstanding"),
            "next_payout_date": next_payout["next_payout_date"] if next_payout else None,
            "next_payout_amount": next_payout["next_payout_amount"] if next_payout else 0,
            "next_payout_investment": next_payout["name"] if next_payout else None,
        },
        "investments": investments,
    }


def get_investment_detail(investment_id: str) -> Dict[str, Any]:
    doc = service._get_existing_investor_flow(investment_id)
    schedule = current_schedule(doc)
    payout_dates = _payout_dates([r.payout_entry for r in schedule])

    return {
        **{f: doc.get(f) for f in INVESTMENT_FIELDS},
        "investment_product_name": frappe.db.get_value(
            "Custom Investment Product", doc.investment_product, "product_name"
        ) or doc.investment_product,
        "mail_sent": doc.get("mail_sent"),
        "subject": doc.get("subject"),
        "payment_status": _payment_status(doc),
        # The latest renewal (its terms are shown next to the original contract terms).
        "renewal": {f: doc.get(f) for f in RENEWAL_ALL_FIELDS} if doc.get("renewal_status") else None,
        **_investment_figures(doc),
        "funds": [
            {
                "name": r.name,
                "paid_date": r.paid_date,
                "amount": flt(r.amount_paid, 2),
                "mode_of_payment": r.mode_of_payment,
                "reference_number": r.reference_number,
                "record_status": r.get("record_status") or RECORD_STATUS_DRAFT,
                "journal_entry": r.get("journal_entry"),
                "paid_from": r.credit_gl,
                "paid_from_description": r.credit_gl_description,
                "paid_to": r.debit_gl,
                "paid_to_description": r.debit_gl_description,
            }
            for r in sorted(doc.get(FUND_TABLE_FIELD) or [], key=lambda r: (getdate(r.paid_date), r.idx))
        ],
        "schedule": [
            {
                "name": r.name,
                "number": i,
                "payment_date": r.payment_date,
                "principal": flt(r.principal_amount, 2),
                "interest": flt(r.interest_amount, 2),
                "penalty": flt(r.penalty_amount, 2),
                "total": flt(r.total_payment, 2),
                "status": r.status or "Pending",
                "paid_on": payout_dates.get(r.payout_entry),
                "payout_entry": r.payout_entry,
                "accrual_entry": r.accrual_entry,
            }
            for i, r in enumerate(schedule, start=1)
        ],
    }


def get_investor_statement(investor: str, investment: Optional[str] = None) -> Dict[str, Any]:
    """
    Every approved fund (money in from the investor) and every payout (money back to the investor),
    oldest first. Balance = principal the company holds for the investor (funds in - principal returned).
    """
    info = _investor_info(investor)
    filters = {"investor": investor}
    if investment:
        filters["name"] = investment
    names = frappe.get_all(DOCTYPE, filters=filters, pluck="name")

    entries = []
    for name in names:
        doc = frappe.get_doc(DOCTYPE, name)
        for r in doc.get(FUND_TABLE_FIELD) or []:
            if r.get("record_status") != RECORD_STATUS_APPROVED:
                continue
            entries.append({
                "date": r.paid_date,
                "investment": name,
                "type": "Fund received",
                "description": f"{r.mode_of_payment}" + (f" · Ref {r.reference_number}" if r.reference_number else ""),
                "paid_in": flt(r.amount_paid, 2),
                "principal_returned": 0,
                "interest_paid": 0,
                "journal_entry": r.get("journal_entry"),
            })
        schedule = current_schedule(doc)
        payout_dates = _payout_dates([r.payout_entry for r in schedule])
        for i, r in enumerate(schedule, start=1):
            if r.status != ROW_STATUS_PAID:
                continue
            entries.append({
                "date": payout_dates.get(r.payout_entry) or r.payment_date,
                "investment": name,
                "type": "Payout",
                "description": f"Instalment {i} (due {getdate(r.payment_date)})",
                "paid_in": 0,
                "principal_returned": flt(r.principal_amount, 2),
                "interest_paid": flt(flt(r.interest_amount) + flt(r.penalty_amount), 2),
                "journal_entry": r.payout_entry,
            })

    entries.sort(key=lambda e: (getdate(e["date"]), 0 if e["type"] == "Fund received" else 1))
    balance = 0.0
    for e in entries:
        balance = flt(balance + e["paid_in"] - e["principal_returned"], 2)
        e["balance"] = balance

    return {
        "investor": info,
        "investment": investment,
        "entries": entries,
        "totals": {
            "paid_in": flt(sum(e["paid_in"] for e in entries), 2),
            "principal_returned": flt(sum(e["principal_returned"] for e in entries), 2),
            "interest_paid": flt(sum(e["interest_paid"] for e in entries), 2),
            "closing_balance": balance,
        },
    }


def _line_meaning(root_type: str, debit: float, credit: float) -> str:
    """What a Journal Entry line means in plain words."""
    increase = debit > 0
    if root_type == "Asset":
        return "Money came in" if increase else "Money went out"
    if root_type == "Liability":
        return "Amount owed to investor increased" if not increase else "Amount owed to investor decreased"
    if root_type == "Expense":
        return "Expense recorded" if increase else "Expense reversed"
    if root_type == "Income":
        return "Income recorded" if not increase else "Income reversed"
    if root_type == "Equity":
        return "Equity increased" if not increase else "Equity decreased"
    return ""


def get_journal_entry_detail(journal_entry: str) -> Dict[str, Any]:
    if not frappe.db.exists("Journal Entry", journal_entry):
        raise frappe.DoesNotExistError(f"Journal Entry '{journal_entry}' does not exist.")
    je = frappe.get_doc("Journal Entry", journal_entry)
    accounts = {
        a.name: a
        for a in frappe.get_all(
            "Account",
            filters={"name": ["in", [line.account for line in je.accounts]]},
            fields=["name", "account_name", "account_number", "root_type", "account_type"],
        )
    }
    party_names = service._get_names(
        "Customer", "customer_name", [line.party for line in je.accounts if line.party_type == "Customer"]
    )

    lines = []
    for line in je.accounts:
        account = accounts.get(line.account)
        debit, credit = flt(line.debit_in_account_currency, 2), flt(line.credit_in_account_currency, 2)
        root_type = account.root_type if account else ""
        lines.append({
            "account": line.account,
            "account_name": account.account_name if account else line.account,
            "account_number": account.account_number if account else None,
            "root_type": root_type,
            "party": party_names.get(line.party) or line.party,
            "debit": debit,
            "credit": credit,
            "meaning": _line_meaning(root_type, debit, credit),
        })

    return {
        "name": je.name,
        "posting_date": je.posting_date,
        "status": {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(je.docstatus, ""),
        "reference_no": je.cheque_no,
        "remark": je.user_remark,
        "total_debit": flt(je.total_debit, 2),
        "total_credit": flt(je.total_credit, 2),
        "lines": lines,
    }
