import datetime
import frappe
from frappe.utils import flt, cint, getdate, nowdate
from pypika import functions as pypika_functions
from pypika.enums import DatePart
from frappe.query_builder.functions import Sum
from collections import defaultdict

from .utils import (
    PAR_BUCKETS,
    RISK_GRADE_BUCKETS,
    PENDING_APPROVAL_STATUSES,
    parse_dashboard_filters,
    filter_subset,
    date_range_filter,
    apply_filters,
    fetch_sum_totals,
    month_label,
    get_company_loan_classifications,
)


def get_dashboard_summary(args):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = (
        period["from_date"],
        period["to_date"],
        period["filters"],
    )

    total_loans = frappe.db.count(
        "Loan",
        {
            **filter_subset("Loan", filters),
            "creation": date_range_filter(from_date, to_date),
            "docstatus": 1,
        },
    )

    active_customers = frappe.db.count(
        "Customer", {"disabled": 0, "creation": ["<=", to_date]}
    )

    disbursement_totals = fetch_sum_totals(
        "Loan Disbursement",
        ["disbursed_amount"],
        "disbursement_date",
        from_date,
        to_date,
        {**filter_subset("Loan Disbursement", filters), "docstatus": 1},
    )

    pending_filters = {
        **filter_subset("Custom Loan Application", filters),
        "status": ["in", PENDING_APPROVAL_STATUSES],
    }

    if from_date and to_date:
        pending_filters["application_date"] = date_range_filter(from_date, to_date)

    pending_applications = frappe.db.count("Custom Loan Application", pending_filters)

    return {
        "total_loans": total_loans,
        "active_customers": active_customers,
        "total_disbursed": disbursement_totals["disbursed_amount"],
        "pending_applications": pending_applications,
    }


def get_dashboard_charts(args):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = (
        period["from_date"],
        period["to_date"],
        period["filters"],
    )
    snapshot = get_loan_portfolio_snapshot(to_date, filters)

    return {
        "collection_efficiency": _build_collection_efficiency(
            from_date, to_date, filters
        ),
        "npa": _build_npa(snapshot),
        "portfolio_classification": _build_portfolio_classification(
            snapshot
        ),  # The new dynamic payload
        "disbursement_vs_collection_trend": _build_disbursement_vs_collection_trend(
            from_date, to_date, filters
        ),
    }


def _build_collection_efficiency(from_date, to_date, filters):
    # 1. Fetch Expected Demand and Outstanding from Loan Demand
    demand = frappe.qb.DocType("Loan Demand")
    demand_query = (
        frappe.qb.from_(demand)
        .select(
            Sum(demand.demand_amount).as_("demand"),
            Sum(demand.outstanding_amount).as_("outstanding"),
        )
        .where(demand.docstatus == 1)
    )

    if from_date:
        demand_query = demand_query.where(
            demand.demand_date.between(from_date, to_date)
        )
    else:
        demand_query = demand_query.where(demand.demand_date <= to_date)

    demand_query = apply_filters(
        demand_query, demand, filter_subset("Loan Demand", filters)
    )

    demand_result = demand_query.run(as_dict=True)
    demand_amount = flt(demand_result[0].get("demand")) if demand_result else 0.0
    outstanding = flt(demand_result[0].get("outstanding")) if demand_result else 0.0

    lr = frappe.qb.DocType("Loan Repayment")
    lr_query = (
        frappe.qb.from_(lr)
        .select(Sum(lr.amount_paid).as_("collected"))
        .where(lr.docstatus == 1)
    )

    if from_date:
        lr_query = lr_query.where(lr.posting_date.between(from_date, to_date))
    else:
        lr_query = lr_query.where(lr.posting_date <= to_date)

    lr_query = apply_filters(lr_query, lr, filter_subset("Loan Repayment", filters))

    lr_result = lr_query.run(as_dict=True)
    collected = flt(lr_result[0].get("collected")) if lr_result else 0.0

    # 3. Calculate Efficiency Rate
    rate_pct = round((collected / demand_amount) * 100, 2) if demand_amount > 0 else 0.0

    return {
        "rate_pct": rate_pct,
        "collected": collected,
        "demand": demand_amount,
        "outstanding": outstanding,
    }


def get_loan_portfolio_snapshot(to_date, filters):
    # Get the company to fetch specific classifications (defaulting to user's company if none selected)
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        raise frappe.ValidationError(
            "Company is required to fetch dynamic classifications."
        )

    dynamic_buckets = get_company_loan_classifications(company)
    print("🚀 ~ get_loan_portfolio_snapshot ~ dynamic_buckets:", dynamic_buckets)

    loan = frappe.qb.DocType("Loan")
    outstanding_expr = loan.total_payment - loan.total_amount_paid

    query = (
        frappe.qb.from_(loan)
        .select(
            loan.days_past_due,
            outstanding_expr.as_("outstanding_amount"),
            loan.is_npa,
            loan.written_off_amount,
        )
        .where(loan.docstatus == 1)
        .where(outstanding_expr > 0)
    )

    if to_date:
        query = query.where(loan.creation <= to_date)

    query = apply_filters(query, loan, filter_subset("Loan", filters))
    loan_rows = query.run(as_dict=True)

    total_portfolio = 0.0
    gross_npa_amount = 0.0
    written_off_in_npa = 0.0
    overdue_amount = 0.0

    for row in loan_rows:
        outstanding_amount = flt(row.outstanding_amount)
        days_past_due = cint(row.days_past_due)

        total_portfolio += outstanding_amount

        if row.is_npa:
            gross_npa_amount += outstanding_amount
            written_off_in_npa += flt(row.written_off_amount)

        if days_past_due > 0:
            overdue_amount += outstanding_amount

        placed = False
        for b in dynamic_buckets:
            if days_past_due >= b["min_dpd"] and days_past_due <= b["max_dpd"]:
                b["amount"] += outstanding_amount
                b["provision_amount"] += outstanding_amount * (
                    b["provision_rate"] / 100.0
                )
                placed = True
                break

        if (
            not placed
            and dynamic_buckets
            and days_past_due > dynamic_buckets[-1]["max_dpd"]
        ):
            highest_bucket = dynamic_buckets[-1]
            highest_bucket["amount"] += outstanding_amount
            highest_bucket["provision_amount"] += outstanding_amount * (
                highest_bucket["provision_rate"] / 100.0
            )

    return {
        "total_portfolio": total_portfolio,
        "gross_npa_amount": gross_npa_amount,
        "written_off_in_npa": written_off_in_npa,
        "overdue_amount": overdue_amount,
        "classification_buckets": dynamic_buckets,
    }


def _build_npa(snapshot):
    total_portfolio = snapshot["total_portfolio"]
    gross_npa_amount = snapshot["gross_npa_amount"]

    # Net NPA = Gross NPA - Provisions (or in this case, written off amount in NPA)
    net_npa_amount = max(gross_npa_amount - snapshot["written_off_in_npa"], 0)

    gross_npa_pct = (
        round((gross_npa_amount / total_portfolio) * 100, 2)
        if total_portfolio > 0
        else 0.0
    )
    net_npa_pct = (
        round((net_npa_amount / total_portfolio) * 100, 2)
        if total_portfolio > 0
        else 0.0
    )

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
            "pct": (
                round((par_bucket_amounts[bucket["label"]] / total_at_risk) * 100, 2)
                if total_at_risk
                else 0
            ),
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
            "pct": (
                round((risk_bucket_amounts[bucket["label"]] / total_portfolio) * 100, 2)
                if total_portfolio
                else 0
            ),
        }
        for bucket in RISK_GRADE_BUCKETS
    ]
    return {"total_portfolio": total_portfolio, "grades": grades}


def _fetch_monthly_totals(
    doctype, amount_field, date_field, from_date, to_date, filters
):
    doc = frappe.qb.DocType(doctype)
    year_expr = pypika_functions.Extract(DatePart.year, doc[date_field])
    month_expr = pypika_functions.Extract(DatePart.month, doc[date_field])

    query = (
        frappe.qb.from_(doc)
        .select(
            year_expr.as_("year"),
            month_expr.as_("month"),
            Sum(doc[amount_field]).as_("total"),
        )
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
    # Fetch disbursement data
    disbursement_rows = _fetch_monthly_totals(
        "Loan Disbursement",
        "disbursed_amount",
        "disbursement_date",
        from_date,
        to_date,
        filter_subset("Loan Disbursement", filters),
    )

    # Fetch collection data
    collection_rows = _fetch_monthly_totals(
        "Loan Repayment",
        "amount_paid",
        "posting_date",
        from_date,
        to_date,
        filter_subset("Loan Repayment", filters),
    )

    # Use defaultdict to automatically initialize missing keys
    monthly_totals = defaultdict(lambda: {"disbursement": 0.0, "collection": 0.0})

    # Populate disbursement totals
    for row in disbursement_rows:
        key = (int(row.year), int(row.month))
        monthly_totals[key]["disbursement"] = flt(row.total)

    # Populate collection totals
    for row in collection_rows:
        key = (int(row.year), int(row.month))
        monthly_totals[key]["collection"] = flt(row.total)

    # Build the final sorted trend list
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
    from_date, to_date, filters = (
        period["from_date"],
        period["to_date"],
        period["filters"],
    )

    disbursement_rows = frappe.get_all(
        "Loan Disbursement",
        filters={
            **filter_subset("Loan Disbursement", filters),
            "disbursement_date": date_range_filter(from_date, to_date),
            "docstatus": 1,
        },
        fields=["loan_product", "disbursement_date", "disbursed_amount"],
    )

    snapshot = get_loan_portfolio_snapshot(to_date, filters)

    return {
        "top_loan_product": _build_top_loan_product(disbursement_rows),
        "highest_disbursement": _build_highest_disbursement_month(disbursement_rows),
        "avg_approval_time": None,
        "overdue_loans": _build_overdue_summary(snapshot),
        "active_agents": None,
    }


def _build_portfolio_classification(snapshot):
    buckets = snapshot["classification_buckets"]
    total_portfolio = snapshot["total_portfolio"]
    
    formatted_grades = []
    
    for b in buckets:
        pct = round((b["amount"] / total_portfolio) * 100, 2) if total_portfolio > 0 else 0.0
        
        formatted_grades.append({
            "label": b["name"],
            "code": b["code"],
            "amount": flt(b["amount"], 2),
            "provision_amount": flt(b["provision_amount"], 2),
            "pct": pct
        })
        
    return {
        "total_portfolio": flt(total_portfolio, 2),
        "classifications": formatted_grades
    }


def _build_top_loan_product(disbursement_rows):
    if not disbursement_rows:
        return {"loan_product": None, "amount": 0, "pct_of_total": 0}

    totals_by_product = {}
    total_disbursed = 0

    for row in disbursement_rows:
        amount = flt(row.disbursed_amount)
        totals_by_product[row.loan_product] = (
            totals_by_product.get(row.loan_product, 0) + amount
        )
        total_disbursed += amount

    top_product = max(totals_by_product, key=totals_by_product.get)
    top_amount = totals_by_product[top_product]
    pct_of_total = (
        round((top_amount / total_disbursed) * 100, 2) if total_disbursed else 0
    )

    return {
        "loan_product": top_product,
        "amount": top_amount,
        "pct_of_total": pct_of_total,
    }


def _build_highest_disbursement_month(disbursement_rows):
    if not disbursement_rows:
        return {"amount": 0, "month_label": None}

    totals_by_month = {}
    for row in disbursement_rows:
        month_key = getdate(row.disbursement_date).strftime("%Y-%m")
        totals_by_month[month_key] = totals_by_month.get(month_key, 0) + flt(
            row.disbursed_amount
        )

    top_month_key = max(totals_by_month, key=totals_by_month.get)
    label = datetime.datetime.strptime(top_month_key, "%Y-%m").strftime("%b %Y")

    return {"amount": totals_by_month[top_month_key], "month_label": label}


def _build_overdue_summary(snapshot):
    total_portfolio = snapshot["total_portfolio"]
    overdue_amount = snapshot["overdue_amount"]
    pct_of_total = (
        round((overdue_amount / total_portfolio) * 100, 2) if total_portfolio else 0
    )
    return {"amount": overdue_amount, "pct_of_total": pct_of_total}


def get_pending_approvals(args, page=1, page_size=20):
    period = parse_dashboard_filters(args)
    from_date, to_date, filters = (
        period["from_date"],
        period["to_date"],
        period["filters"],
    )

    query_filters = {
        **filter_subset("Custom Loan Application", filters),
        "status": ["in", PENDING_APPROVAL_STATUSES],
    }

    if from_date and to_date:
        query_filters["application_date"] = date_range_filter(from_date, to_date)

    start = (cint(page) - 1) * cint(page_size)

    rows = frappe.get_all(
        "Custom Loan Application",
        filters=query_filters,
        fields=[
            "name as application_id",
            "first_name",
            "last_name",
            "company_name",
            "application_type",
            "amount",
            "status as current_stage",
            "application_date",
        ],
        order_by="application_date asc",
        limit_start=start,
        limit_page_length=cint(page_size),
    )

    total = frappe.db.count("Custom Loan Application", query_filters)
    today = getdate(nowdate())
    formatted_rows = []

    for row in rows:
        customer_name = row.get("company_name")
        if not customer_name:
            first = row.get("first_name") or ""
            last = row.get("last_name") or ""
            customer_name = f"{first} {last}".strip()

        app_date = (
            getdate(row.get("application_date"))
            if row.get("application_date")
            else today
        )
        pending_days = (today - app_date).days

        formatted_rows.append(
            {
                "application_id": row.get("application_id"),
                "customer_name": customer_name or "Unknown",
                "loan_product": row.get("application_type"),
                "amount": flt(row.get("amount")),
                "current_stage": row.get("current_stage"),
                "pending_since": f"{pending_days} Days",
            }
        )

    return formatted_rows, total

def get_overdue_tasks(args, page=1, page_size=20):
    period = parse_dashboard_filters(args)
    to_date = period["to_date"]
    filters = period["filters"]

    query_filters = {
        **filter_subset("Loan", filters),
        "days_past_due": [">", 0],
        "docstatus": 1,
    }

    if to_date:
        query_filters["creation"] = ["<=", to_date]

    page = max(cint(page), 1)
    page_size = max(cint(page_size), 1)
    start = (page - 1) * page_size

    rows = frappe.get_all(
        "Loan",
        filters=query_filters,
        fields=[
            "name as loan_account",
            "applicant",
            "days_past_due",
            "total_payment",
            "total_amount_paid",
        ],
        order_by="days_past_due desc",
        limit_start=start,
        limit_page_length=page_size,
    )

    applicant_ids = list({
        row.applicant
        for row in rows
        if row.applicant
    })

    customer_map = {}

    if applicant_ids:
        customers = frappe.get_all(
            "Customer",
            filters={
                "name": ["in", applicant_ids],
            },
            fields=[
                "name",
                "customer_name",
            ],
        )

        customer_map = {
            customer.name: customer.customer_name
            for customer in customers
        }

    for row in rows:
        applicant = row.pop("applicant", None)

        row["customer_name"] = customer_map.get(
            applicant,
            applicant,
        )

        days_past_due = cint(row.get("days_past_due"))

        total_payment = flt(row.pop("total_payment"))
        total_amount_paid = flt(row.pop("total_amount_paid"))

        row["amount_overdue"] = max(
            total_payment - total_amount_paid,
            0,
        )

        if days_past_due >= 60:
            row["next_action"] = "Legal Notice"
            row["priority"] = "High"
        elif days_past_due >= 30:
            row["next_action"] = "Agent Follow-up"
            row["priority"] = "Medium"
        else:
            row["next_action"] = "Agent Follow-up"
            row["priority"] = "Low"

    total = frappe.db.count(
        "Loan",
        filters=query_filters,
    )

    return rows, total
