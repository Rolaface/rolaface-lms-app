import datetime
import frappe
from frappe.utils import flt, cint, getdate, nowdate
from pypika import functions as pypika_functions
from pypika.enums import DatePart
from frappe.query_builder.functions import Sum
from .constant import PAR_BUCKETS, RISK_GRADE_BUCKETS, PENDING_APPROVAL_STATUSES
from .utils import (
    parse_dashboard_filters, filter_subset, date_range_filter,
    apply_filters, fetch_sum_totals, month_label,
)


def get_dashboard_summary(args):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = period["from_date"], period["to_date"], period["filters"]

    total_loans = frappe.db.count(
        "Loan",
        {
            **filter_subset("Loan", filters), 
            "posting_date": date_range_filter(from_date, to_date),
            "docstatus": 1
        },
    )

    active_customers = frappe.db.count("Customer", {"disabled": 0}) 

    disbursement_totals = fetch_sum_totals(
        "Loan Disbursement", ["disbursed_amount"], "disbursement_date",
        from_date, to_date, {**filter_subset("Loan Disbursement", filters), "docstatus": 1},
    )

    pending_filters = {
        **filter_subset("Loan Application", filters),
        "status": ["in", PENDING_APPROVAL_STATUSES],
        "posting_date": date_range_filter(from_date, to_date),
        "docstatus": 1,
    }
    pending_applications = frappe.db.count("Loan Application", pending_filters)

    return {
        "total_loans": total_loans,
        "active_customers": active_customers,
        "total_disbursed": disbursement_totals["disbursed_amount"],
        "pending_applications": pending_applications,
    }


def get_loan_portfolio_snapshot(to_date, filters):
    loan_filters = {
        **filter_subset("Loan", filters), 
        "disbursement_date": ["<=", to_date],
        "docstatus": 1
    }
    loan_rows = frappe.get_all(
        "Loan",
        filters=loan_filters,
        fields=["days_past_due", "total_payment", "total_amount_paid", "is_npa", "written_off_amount"],
    )

    total_portfolio = 0
    gross_npa_amount = 0
    written_off_in_npa = 0
    overdue_amount = 0
    par_bucket_amounts = {bucket["label"]: 0 for bucket in PAR_BUCKETS}
    risk_bucket_amounts = {bucket["label"]: 0 for bucket in RISK_GRADE_BUCKETS}

    for row in loan_rows:
        outstanding_amount = max(flt(row.total_payment) - flt(row.total_amount_paid), 0)
        days_past_due = row.days_past_due or 0

        total_portfolio += outstanding_amount

        if row.is_npa:
            gross_npa_amount += outstanding_amount
            written_off_in_npa += flt(row.written_off_amount)

        if days_past_due > 0:
            overdue_amount += outstanding_amount

        for bucket in PAR_BUCKETS:
            if days_past_due >= bucket["min_days"] and (bucket["max_days"] is None or days_past_due <= bucket["max_days"]):
                par_bucket_amounts[bucket["label"]] += outstanding_amount

        for bucket in RISK_GRADE_BUCKETS:
            if days_past_due >= bucket["min_days"] and (bucket["max_days"] is None or days_past_due <= bucket["max_days"]):
                risk_bucket_amounts[bucket["label"]] += outstanding_amount

    return {
        "total_portfolio": total_portfolio,
        "gross_npa_amount": gross_npa_amount,
        "written_off_in_npa": written_off_in_npa,
        "overdue_amount": overdue_amount,
        "par_bucket_amounts": par_bucket_amounts,
        "risk_bucket_amounts": risk_bucket_amounts,
    }


def get_dashboard_charts(args):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = period["from_date"], period["to_date"], period["filters"]
    snapshot = get_loan_portfolio_snapshot(to_date, filters)

    return {
        "collection_efficiency": _build_collection_efficiency(from_date, to_date, filters),
        "npa": _build_npa(snapshot),
        "par_buckets": _build_par_buckets(snapshot),
        "disbursement_vs_collection_trend": _build_disbursement_vs_collection_trend(from_date, to_date, filters),
        "risk_grade_matrix": _build_risk_grade_matrix(snapshot),
    }


def _build_collection_efficiency(from_date, to_date, filters):
    totals = fetch_sum_totals(
        "Loan Repayment", ["payable_amount", "amount_paid"], "due_date",
        from_date, to_date, {**filter_subset("Loan Repayment", filters), "docstatus": 1},
    )
    demand = totals["payable_amount"]
    collected = totals["amount_paid"]
    rate_pct = round((collected / demand) * 100, 2) if demand else 0

    return {"rate_pct": rate_pct, "collected": collected, "demand": demand}


def _build_npa(snapshot):
    total_portfolio = snapshot["total_portfolio"]
    gross_npa_amount = snapshot["gross_npa_amount"]
    net_npa_amount = max(gross_npa_amount - snapshot["written_off_in_npa"], 0)

    gross_npa_pct = round((gross_npa_amount / total_portfolio) * 100, 2) if total_portfolio else 0
    net_npa_pct = round((net_npa_amount / total_portfolio) * 100, 2) if total_portfolio else 0

    return {
        "gross_npa_pct": gross_npa_pct,
        "net_npa_pct": net_npa_pct,
        "gross_npa_amount": gross_npa_amount,
        "net_npa_amount": net_npa_amount,
    }


def _build_par_buckets(snapshot):
    par_bucket_amounts = snapshot["par_bucket_amounts"]
    total_at_risk = sum(par_bucket_amounts.values())

    buckets = [
        {
            "label": bucket["label"],
            "amount": par_bucket_amounts[bucket["label"]],
            "pct": round((par_bucket_amounts[bucket["label"]] / total_at_risk) * 100, 2) if total_at_risk else 0,
        }
        for bucket in PAR_BUCKETS
    ]

    return {"total_at_risk": total_at_risk, "buckets": buckets}


def _build_risk_grade_matrix(snapshot):
    risk_bucket_amounts = snapshot["risk_bucket_amounts"]
    total_portfolio = snapshot["total_portfolio"]

    grades = [
        {
            "risk_grade": bucket["label"],
            "amount": risk_bucket_amounts[bucket["label"]],
            "pct": round((risk_bucket_amounts[bucket["label"]] / total_portfolio) * 100, 2) if total_portfolio else 0,
        }
        for bucket in RISK_GRADE_BUCKETS
    ]

    return {"total_portfolio": total_portfolio, "grades": grades}


def _fetch_monthly_totals(doctype, amount_field, date_field, from_date, to_date, filters):
    doc = frappe.qb.DocType(doctype)
    year_expr = pypika_functions.Extract(DatePart.year, doc[date_field])
    month_expr = pypika_functions.Extract(DatePart.month, doc[date_field])

    query = (
        frappe.qb.from_(doc)
        .select(year_expr.as_("year"), month_expr.as_("month"), Sum(doc[amount_field]).as_("total"))
        .where(doc.docstatus == 1)
        .groupby(year_expr, month_expr)
        .orderby(year_expr)
        .orderby(month_expr)
    )

    if from_date is None:
        query = query.where(doc[date_field] <= to_date)
    else:
        query = query.where(doc[date_field].between(from_date, to_date))

    query = apply_filters(query, doc, filters)
    return query.run(as_dict=True)


def _build_disbursement_vs_collection_trend(from_date, to_date, filters):
    disbursement_rows = _fetch_monthly_totals(
        "Loan Disbursement", "disbursed_amount", "disbursement_date",
        from_date, to_date, filter_subset("Loan Disbursement", filters),
    )
    collection_rows = _fetch_monthly_totals(
        "Loan Repayment", "amount_paid", "posting_date",
        from_date, to_date, filter_subset("Loan Repayment", filters),
    )

    monthly_totals = {}

    for row in disbursement_rows:
        key = (int(row.year), int(row.month))
        monthly_totals.setdefault(key, {"disbursement": 0, "collection": 0})
        monthly_totals[key]["disbursement"] = flt(row.total)

    for row in collection_rows:
        key = (int(row.year), int(row.month))
        monthly_totals.setdefault(key, {"disbursement": 0, "collection": 0})
        monthly_totals[key]["collection"] = flt(row.total)

    trend = [
        {
            "period": month_label(year, month),
            "disbursement": monthly_totals[(year, month)]["disbursement"],
            "collection": monthly_totals[(year, month)]["collection"],
        }
        for year, month in sorted(monthly_totals.keys())
    ]

    return trend


def get_quick_insights(args):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = period["from_date"], period["to_date"], period["filters"]

    disbursement_rows = frappe.get_all(
        "Loan Disbursement",
        filters={
            **filter_subset("Loan Disbursement", filters), 
            "disbursement_date": date_range_filter(from_date, to_date),
            "docstatus": 1
        },
        fields=["loan_product", "disbursement_date", "disbursed_amount"],
    )

    snapshot = get_loan_portfolio_snapshot(to_date, filters)

    return {
        "top_loan_product": _build_top_loan_product(disbursement_rows),
        "highest_disbursement": _build_highest_disbursement_month(disbursement_rows),
        "avg_approval_time": _build_avg_approval_time(from_date, to_date, filters),
        "overdue_loans": _build_overdue_summary(snapshot),
        "active_agents": None,
    }


def _build_top_loan_product(disbursement_rows):
    if not disbursement_rows:
        return {"loan_product": None, "amount": 0, "pct_of_total": 0}

    totals_by_product = {}
    total_disbursed = 0

    for row in disbursement_rows:
        amount = flt(row.disbursed_amount)
        totals_by_product[row.loan_product] = totals_by_product.get(row.loan_product, 0) + amount
        total_disbursed += amount

    top_product = max(totals_by_product, key=totals_by_product.get)
    top_amount = totals_by_product[top_product]
    pct_of_total = round((top_amount / total_disbursed) * 100, 2) if total_disbursed else 0

    return {"loan_product": top_product, "amount": top_amount, "pct_of_total": pct_of_total}


def _build_highest_disbursement_month(disbursement_rows):
    if not disbursement_rows:
        return {"amount": 0, "month_label": None}

    totals_by_month = {}

    for row in disbursement_rows:
        month_key = getdate(row.disbursement_date).strftime("%Y-%m")
        totals_by_month[month_key] = totals_by_month.get(month_key, 0) + flt(row.disbursed_amount)

    top_month_key = max(totals_by_month, key=totals_by_month.get)
    label = datetime.datetime.strptime(top_month_key, "%Y-%m").strftime("%b %Y")

    return {"amount": totals_by_month[top_month_key], "month_label": label}


def _build_avg_approval_time(from_date, to_date, filters):
    loan_doc = frappe.qb.DocType("Loan")
    application_doc = frappe.qb.DocType("Loan Application")

    query = (
        frappe.qb.from_(loan_doc)
        .inner_join(application_doc)
        .on(loan_doc.loan_application == application_doc.name)
        .select(
            loan_doc.posting_date.as_("loan_posting_date"),
            application_doc.posting_date.as_("application_posting_date"),
        )
        .where(loan_doc.docstatus == 1)
        .where(application_doc.docstatus == 1)
    )

    if from_date is None:
        query = query.where(loan_doc.posting_date <= to_date)
    else:
        query = query.where(loan_doc.posting_date.between(from_date, to_date))

    query = apply_filters(query, loan_doc, filter_subset("Loan", filters))
    rows = query.run(as_dict=True)

    if not rows:
        return {"avg_days": 0}

    total_days = sum(
        (getdate(row.loan_posting_date) - getdate(row.application_posting_date)).days
        for row in rows
    )
    avg_days = round(total_days / len(rows), 1)

    return {"avg_days": avg_days}


def _build_overdue_summary(snapshot):
    total_portfolio = snapshot["total_portfolio"]
    overdue_amount = snapshot["overdue_amount"]
    pct_of_total = round((overdue_amount / total_portfolio) * 100, 2) if total_portfolio else 0

    return {"amount": overdue_amount, "pct_of_total": pct_of_total}


def get_pending_approvals(args, page=1, page_size=20):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = period["from_date"], period["to_date"], period["filters"]

    query_filters = {
        **filter_subset("Loan Application", filters),
        "status": ["in", PENDING_APPROVAL_STATUSES],
        "posting_date": date_range_filter(from_date, to_date),
        "docstatus": 1,
    }
    start = (cint(page) - 1) * cint(page_size)

    rows = frappe.get_all(
        "Loan Application",
        filters=query_filters,
        fields=[
            "name as application_id",
            "applicant_name as customer_name",
            "loan_product",
            "loan_amount as amount",
            "status as current_stage",
            "posting_date as pending_since",
        ],
        order_by="posting_date asc",
        limit_start=start,
        limit_page_length=cint(page_size),
    )

    total = frappe.db.count("Loan Application", query_filters)

    today = getdate(nowdate())
    for row in rows:
        row["pending_days"] = (today - getdate(row["pending_since"])).days

    return rows, total


def get_overdue_tasks(args, page=1, page_size=20):
    period = parse_dashboard_filters(args)
    filters = period["filters"]

    query_filters = {
        **filter_subset("Loan", filters), 
        "days_past_due": [">", 0],
        "docstatus": 1
    }
    start = (cint(page) - 1) * cint(page_size)

    rows = frappe.get_all(
        "Loan",
        filters=query_filters,
        fields=[
            "name as loan_account",
            "applicant_name as customer_name",
            "days_past_due",
            "total_payment",
            "total_amount_paid",
        ],
        order_by="days_past_due desc",
        limit_start=start,
        limit_page_length=cint(page_size),
    )

    total = frappe.db.count("Loan", query_filters)

    for row in rows:
        days_past_due = row["days_past_due"] or 0
        row["amount_overdue"] = max(flt(row.pop("total_payment")) - flt(row.pop("total_amount_paid")), 0)
        row["next_action"] = "Legal Notice" if days_past_due >= 60 else "Agent Follow-up"
        row["priority"] = "High" if days_past_due >= 60 else ("Medium" if days_past_due >= 30 else "Low")

    return rows, total