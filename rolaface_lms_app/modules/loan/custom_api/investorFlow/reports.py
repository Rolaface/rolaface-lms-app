"""
Investor Report: one row per investment, with what is due and what has been paid out to the investor.

  Invst Amt    = Investment Amount
  Fund Recv    = received from the investor (approved Fund Receipts)
  Paid out     = paid out to the investor (principal + interest + penalty paid)
  Prin Paid / Int Paid / Penal Paid
               = paid on the current repayment schedule (a Paid EMI counts in full; a Partially Paid EMI is
                 split interest, then penalty, then principal, like the payouts)
  Total Int / Total Penal
               = interest / penalty of the current repayment schedule
  Start date   = paid date of the first approved Fund Receipt (blank until money is received)
  End date     = Maturity Date

Filters: search (investment ID / investor name, mobile, ID, email), status (default: every status except
Cancelled), product, start date from / to. Totals, status counts and insights cover every filtered investment;
the rows are paginated (page_size 0 = all rows, used by the export).

Insights (as of today):
  efficiency          - paid on the EMIs due up to today / what those EMIs total
  overdue             - unpaid EMIs whose date has passed: count, investments, amount, oldest; top 5 investments
  trend               - per month (last 6 and next 3): scheduled (EMIs due) vs actual (approved payouts, by value date)
  upcoming_maturities - maturity date in the next 90 days (not Matured): count, outstanding; the 5 soonest
  top_investors / top_products - the 5 largest by amount invested
"""
import frappe
from typing import Any, Dict, List
from frappe.utils import add_months, date_diff, flt, getdate, nowdate

from .constant import DOCTYPE, FUND_RECORD_DOCTYPE, FUND_TABLE_FIELD, SCHEDULE_TABLE_FIELD, RECORD_STATUS_APPROVED
from .utils import _as_list, schedule_version
from . import service

SCHEDULE_DOCTYPE = "Custom Investor Earning Schedule"
PAYOUT_DOCTYPE = "Custom Investor Payouts"
MATURITY_WINDOW_DAYS = 90
TREND_PAST_MONTHS = 6
TREND_NEXT_MONTHS = 3
TOP_N = 5
DEFAULT_EXCLUDED_STATUSES = ["Cancelled"]
AMOUNT_FIELDS = [
    "investment_amount", "fund_received", "amount_paid", "principal_paid", "total_interest", "interest_paid",
    "total_penalty", "penalty_paid", "total_due", "outstanding",
]


def _paid_parts(row) -> Dict[str, float]:
    """Interest / penalty / principal paid on one EMI."""
    interest, penalty, principal = flt(row.interest_amount, 2), flt(row.penalty_amount, 2), flt(row.principal_amount, 2)
    if row.status == "Paid":
        return {"interest": interest, "penalty": penalty, "principal": principal}
    paid = flt(row.paid_amount, 2)
    paid_interest = min(paid, interest)
    paid_penalty = min(max(paid - interest, 0), penalty)
    paid_principal = min(max(paid - interest - penalty, 0), principal)
    return {"interest": paid_interest, "penalty": paid_penalty, "principal": paid_principal}


def _current_rows(rows: List) -> List:
    if not rows:
        return []
    latest = max(schedule_version(r) for r in rows)
    return [r for r in rows if schedule_version(r) == latest]


def _report_rows(args: Dict[str, Any]):
    """(rows, current schedule rows by investment)."""
    filters: Dict[str, Any] = {}
    statuses = [s for s in _as_list(args.get("status")) if s] if args.get("status") else []
    filters["status"] = ["in", statuses] if statuses else ["not in", DEFAULT_EXCLUDED_STATUSES]
    if args.get("product"):
        filters["investment_product"] = args.get("product")
    or_filters = None
    search = (args.get("search") or "").strip()
    if search:
        term = f"%{search}%"
        or_filters = [["name", "like", term], ["investor", "like", term]]
        investor_ids = service._matching_investors(term)
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    investments = frappe.get_all(
        DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=["name", "investor", "investment_product", "investment_amount", "maturity_date", "status",
                "payment_status", "creation"],
        order_by="creation desc",
    )
    if not investments:
        return [], {}
    names = [i.name for i in investments]

    schedule: Dict[str, List] = {}
    for r in frappe.get_all(
        SCHEDULE_DOCTYPE,
        filters={"parent": ["in", names], "parenttype": DOCTYPE, "parentfield": SCHEDULE_TABLE_FIELD},
        fields=["parent", "version", "payment_date", "principal_amount", "interest_amount", "penalty_amount",
                "total_payment", "paid_amount", "status"],
        parent_doctype=DOCTYPE,
    ):
        schedule.setdefault(r.parent, []).append(r)

    start_dates: Dict[str, Any] = {}
    received: Dict[str, float] = {}
    for f in frappe.get_all(
        FUND_RECORD_DOCTYPE,
        filters={"parent": ["in", names], "parenttype": DOCTYPE, "parentfield": FUND_TABLE_FIELD,
                 "record_status": RECORD_STATUS_APPROVED},
        fields=["parent", "paid_date", "amount_paid"],
        parent_doctype=DOCTYPE,
    ):
        received[f.parent] = flt(received.get(f.parent, 0) + flt(f.amount_paid), 2)
        if f.paid_date and (f.parent not in start_dates or getdate(f.paid_date) < start_dates[f.parent]):
            start_dates[f.parent] = getdate(f.paid_date)

    investor_names = service._get_names("Customer", "customer_name", list({i.investor for i in investments}))
    product_names = service._get_names(
        "Custom Investment Product", "product_name", list({i.investment_product for i in investments if i.investment_product})
    )

    start_from = getdate(args.get("start_from")) if args.get("start_from") else None
    start_to = getdate(args.get("start_to")) if args.get("start_to") else None

    rows = []
    current_by_inv: Dict[str, List] = {}
    for inv in investments:
        start = start_dates.get(inv.name)
        if (start_from or start_to) and (
            not start or (start_from and start < start_from) or (start_to and start > start_to)
        ):
            continue
        current = _current_rows(schedule.get(inv.name, []))
        current_by_inv[inv.name] = current
        paid = {"interest": 0.0, "penalty": 0.0, "principal": 0.0}
        for r in current:
            for k, v in _paid_parts(r).items():
                paid[k] += v
        total_principal = flt(sum(flt(r.principal_amount) for r in current), 2)
        total_interest = flt(sum(flt(r.interest_amount) for r in current), 2)
        total_penalty = flt(sum(flt(r.penalty_amount) for r in current), 2)
        amount_paid = flt(paid["principal"] + paid["interest"] + paid["penalty"], 2)
        total_due = flt(total_principal + total_interest + total_penalty, 2)
        rows.append({
            "investment_id": inv.name,
            "investor_id": inv.investor,
            "investor": investor_names.get(inv.investor) or inv.investor,
            "product": product_names.get(inv.investment_product) or inv.investment_product,
            "status": inv.status,
            "payment_status": inv.payment_status,
            "investment_amount": flt(inv.investment_amount, 2),
            "fund_received": received.get(inv.name, 0.0),
            "amount_paid": amount_paid,
            "principal_paid": flt(paid["principal"], 2),
            "total_interest": total_interest,
            "interest_paid": flt(paid["interest"], 2),
            "total_penalty": total_penalty,
            "penalty_paid": flt(paid["penalty"], 2),
            "total_due": total_due,
            "outstanding": flt(total_due - amount_paid, 2),
            "emis_total": len(current),
            "emis_paid": len([r for r in current if r.status == "Paid"]),
            "start_date": str(start) if start else None,
            "end_date": str(getdate(inv.maturity_date)) if inv.maturity_date else None,
        })
    return rows, current_by_inv


def _remaining(row) -> float:
    if row.status == "Paid":
        return 0.0
    return max(flt(flt(row.total_payment) - flt(row.paid_amount), 2), 0.0)


def _top(rows: List[Dict[str, Any]], key: str, label_key: str) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.get(key) or "-"
        g = groups.setdefault(k, {"id": k, "name": r.get(label_key) or k, "invested": 0.0, "paid_out": 0.0,
                                  "investments": 0})
        g["invested"] = flt(g["invested"] + r["investment_amount"], 2)
        g["paid_out"] = flt(g["paid_out"] + r["amount_paid"], 2)
        g["investments"] += 1
    return sorted(groups.values(), key=lambda g: -g["invested"])[:TOP_N]


def _insights(rows: List[Dict[str, Any]], current_by_inv: Dict[str, List]) -> Dict[str, Any]:
    today = getdate(nowdate())
    by_id = {r["investment_id"]: r for r in rows}

    # Efficiency and overdue (EMIs due up to today)
    due_to_date = paid_on_due = 0.0
    overdue_emis = 0
    overdue_amount = 0.0
    oldest_days = 0
    overdue_by_inv: Dict[str, Dict[str, Any]] = {}
    for inv_id, current in current_by_inv.items():
        for row in current:
            if not row.payment_date or getdate(row.payment_date) > today:
                continue
            total = flt(row.total_payment, 2)
            left = _remaining(row)
            due_to_date += total
            paid_on_due += total - left
            if left > 0 and getdate(row.payment_date) < today:
                days = date_diff(today, row.payment_date)
                overdue_emis += 1
                overdue_amount += left
                oldest_days = max(oldest_days, days)
                o = overdue_by_inv.setdefault(inv_id, {
                    "investment_id": inv_id, "investor": by_id[inv_id]["investor"], "amount": 0.0, "emis": 0, "days": 0,
                })
                o["amount"] = flt(o["amount"] + left, 2)
                o["emis"] += 1
                o["days"] = max(o["days"], days)

    # Scheduled vs actual, per month
    first_month = getdate(add_months(today, -(TREND_PAST_MONTHS - 1))).replace(day=1)
    months = [getdate(add_months(first_month, i)) for i in range(TREND_PAST_MONTHS + TREND_NEXT_MONTHS)]
    key = lambda d: getdate(d).strftime("%Y-%m")
    trend = {key(m): {"month": key(m), "scheduled": 0.0, "actual": 0.0} for m in months}
    for current in current_by_inv.values():
        for row in current:
            if row.payment_date and key(row.payment_date) in trend:
                trend[key(row.payment_date)]["scheduled"] += flt(row.total_payment, 2)
    if by_id:
        for p in frappe.get_all(
            PAYOUT_DOCTYPE,
            filters={"parent": ["in", list(by_id)], "parenttype": DOCTYPE, "record_status": "Approved"},
            fields=["value_date", "payment_amount"],
            parent_doctype=DOCTYPE,
        ):
            if p.value_date and key(p.value_date) in trend:
                trend[key(p.value_date)]["actual"] += flt(p.payment_amount, 2)
    current_month = key(today)
    trend_rows = [
        {**t, "scheduled": flt(t["scheduled"], 2),
         # Months still to come have no actual payouts yet.
         "actual": flt(t["actual"], 2) if t["month"] <= current_month else None}
        for t in trend.values()
    ]

    # Upcoming maturities
    upcoming = sorted(
        (r for r in rows
         if r["end_date"] and r["status"] not in ("Matured", "Cancelled")
         and 0 <= date_diff(r["end_date"], today) <= MATURITY_WINDOW_DAYS),
        key=lambda r: r["end_date"],
    )

    return {
        "efficiency": {
            "due_to_date": flt(due_to_date, 2),
            "paid": flt(paid_on_due, 2),
            "rate_pct": flt(paid_on_due / due_to_date * 100, 2) if due_to_date else 0.0,
        },
        "overdue": {
            "emis": overdue_emis,
            "investments": len(overdue_by_inv),
            "amount": flt(overdue_amount, 2),
            "oldest_days": oldest_days,
            "top": sorted(overdue_by_inv.values(), key=lambda o: -o["amount"])[:TOP_N],
        },
        "trend": trend_rows,
        "upcoming_maturities": {
            "window_days": MATURITY_WINDOW_DAYS,
            "count": len(upcoming),
            "outstanding": flt(sum(r["outstanding"] for r in upcoming), 2),
            "items": [
                {"investment_id": r["investment_id"], "investor": r["investor"], "end_date": r["end_date"],
                 "days_left": date_diff(r["end_date"], today), "investment_amount": r["investment_amount"],
                 "outstanding": r["outstanding"]}
                for r in upcoming[:TOP_N]
            ],
        },
        "top_investors": _top(rows, "investor_id", "investor"),
        "top_products": _top(rows, "product", "product"),
    }


def get_investor_report(args: Dict[str, Any], page: int, page_size: int) -> Dict[str, Any]:
    rows, current_by_inv = _report_rows(args)
    total = len(rows)
    totals = {f: flt(sum(r[f] for r in rows), 2) for f in AMOUNT_FIELDS}
    status_counts: Dict[str, int] = {}
    for r in rows:
        status_counts[r["status"] or "Draft"] = status_counts.get(r["status"] or "Draft", 0) + 1

    if page_size > 0:
        total_pages = max((total + page_size - 1) // page_size, 1)
        page_rows = rows[(page - 1) * page_size: page * page_size]
    else:
        total_pages, page_rows = 1, rows
    return {
        "rows": page_rows,
        "totals": {**totals, "investments": total, "investors": len({r["investor_id"] for r in rows})},
        "status_counts": status_counts,
        "insights": _insights(rows, current_by_inv),
        "pagination": {
            "page": page, "page_size": page_size, "total": total, "total_pages": total_pages,
            "has_next": page < total_pages, "has_prev": page > 1,
        },
    }
