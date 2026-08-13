import frappe
from frappe.query_builder import DocType, Order
from frappe.query_builder.functions import Sum, Max, Min
from frappe.utils import getdate, flt, nowdate, formatdate
from typing import Dict, Any, List, Tuple
from collections import defaultdict

def generate_loan_statement(loan_id: str, from_date: str = None, to_date: str = None) -> Dict[str, Any]:

    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    loan_doc = frappe.get_doc("Loan", loan_id)
    start_date, end_date = _resolve_date_range(loan_doc, from_date, to_date)

    transactions = _fetch_ledger_transactions(loan_id, end_date)
    processed_data = _process_ledger(transactions, start_date, end_date)
    
    snapshot = _build_snapshot_metrics(loan_doc, processed_data["summary"]["total_disbursed"])
    aging_summary = _calculate_aging_summary(loan_id)

    return {
        "snapshot": snapshot,
        "summary": processed_data["summary"],
        "statement": processed_data["statement"],
        "balance_trend": processed_data["balance_trend"],
        "cash_flow": processed_data["cash_flow"],
        "aging_summary": aging_summary
    }


def _resolve_date_range(loan_doc: Any, requested_from: str, requested_to: str) -> Tuple[Any, Any]:

    resolved_from = getdate(requested_from) if requested_from else loan_doc.repayment_start_date
    
    if requested_to:
        resolved_to = getdate(requested_to)
    else:
        lrs = DocType("Loan Repayment Schedule")
        rs = DocType("Repayment Schedule")
        result = (
            frappe.qb.from_(rs)
            .join(lrs).on(rs.parent == lrs.name)
            .select(Max(rs.payment_date))
            .where((lrs.loan == loan_doc.name) & (lrs.docstatus == 1))
            .run()
        )
        resolved_to = getdate(result[0][0]) if result and result[0][0] else getdate(nowdate())
        
    return getdate(resolved_from), getdate(resolved_to)


def _fetch_ledger_transactions(loan_id: str, end_date: Any) -> List[Dict[str, Any]]:

    transactions = []

    ld = DocType("Loan Disbursement")
    disbursements = (
        frappe.qb.from_(ld)
        .select(
            ld.disbursement_date.as_("posting_date"),
            ld.name.as_("reference_no"),
            ld.disbursed_amount.as_("amount")
        )
        .where((ld.against_loan == loan_id) & (ld.docstatus == 1) & (ld.disbursement_date <= end_date))
        .run(as_dict=True)
    )
    for d in disbursements:
        transactions.append({
            "date": d.posting_date,
            "particulars": "Loan Disbursement",
            "reference_no": d.reference_no,
            "transaction_type": "Disbursal",
            "debit": flt(d.amount),
            "credit": 0.0
        })

    lia = DocType("Loan Interest Accrual")
    accruals = (
        frappe.qb.from_(lia)
        .select(
            lia.posting_date,
            lia.name.as_("reference_no"),
            lia.interest_amount,
            lia.additional_interest_amount
        )
        .where((lia.loan == loan_id) & (lia.docstatus == 1) & (lia.posting_date <= end_date))
        .run(as_dict=True)
    )
    for a in accruals:
        if flt(a.interest_amount) > 0:
            transactions.append({
                "date": getdate(a.posting_date),
                "particulars": "Interest Accrued",
                "reference_no": a.reference_no,
                "transaction_type": "Interest",
                "debit": flt(a.interest_amount),
                "credit": 0.0
            })
        if flt(a.additional_interest_amount) > 0:
            transactions.append({
                "date": getdate(a.posting_date),
                "particulars": "Penalty / Charges",
                "reference_no": a.reference_no,
                "transaction_type": "Charge",
                "debit": flt(a.additional_interest_amount),
                "credit": 0.0
            })

    lr = DocType("Loan Repayment")
    repayments = (
        frappe.qb.from_(lr)
        .select(
            lr.posting_date,
            lr.name.as_("reference_no"),
            lr.amount_paid
        )
        .where((lr.against_loan == loan_id) & (lr.docstatus == 1) & (lr.posting_date <= end_date))
        .run(as_dict=True)
    )
    for r in repayments:
        transactions.append({
            "date": getdate(r.posting_date),
            "particulars": "EMI Payment",
            "reference_no": r.reference_no,
            "transaction_type": "Repayment",
            "debit": 0.0,
            "credit": flt(r.amount_paid)
        })

    transactions.sort(key=lambda x: getdate(x["date"]))
    return transactions


def _process_ledger(transactions: List[Dict[str, Any]], start_date: Any, end_date: Any) -> Dict[str, Any]:

    running_balance = 0.0
    opening_balance = 0.0
    
    summary = {"total_disbursed": 0.0, "total_repayments": 0.0, "total_charges": 0.0}
    statement_lines = []
    
    # Aggregation matrices for charting
    monthly_flow = defaultdict(lambda: {"disbursal": 0.0, "repayment": 0.0, "charges": 0.0})
    monthly_trend = {}

    for txn in transactions:
        txn_date = getdate(txn["date"])
        month_key = formatdate(txn_date, "MMM 'yy")

        running_balance += txn["debit"]
        running_balance -= txn["credit"]
        txn["balance"] = running_balance
        
        monthly_trend[month_key] = running_balance

        if txn_date < start_date:
            opening_balance = running_balance
        else:
            statement_lines.append(txn)
            
            if txn["transaction_type"] == "Disbursal":
                summary["total_disbursed"] += txn["debit"]
                monthly_flow[month_key]["disbursal"] += txn["debit"]
            elif txn["transaction_type"] == "Repayment":
                summary["total_repayments"] += txn["credit"]
                monthly_flow[month_key]["repayment"] += txn["credit"]
            elif txn["transaction_type"] in ["Charge", "Interest"]:
                summary["total_charges"] += txn["debit"]
                monthly_flow[month_key]["charges"] += txn["debit"]

    statement_lines.insert(0, {
        "date": start_date,
        "particulars": "Opening Balance",
        "reference_no": "-",
        "transaction_type": "Opening Balance",
        "debit": 0.0,
        "credit": 0.0,
        "balance": opening_balance
    })

    summary["opening_balance"] = opening_balance
    summary["closing_balance"] = running_balance

    cash_flow_array = [
        {"month": k, "disbursal": v["disbursal"], "repayment": v["repayment"], "charges": v["charges"]}
        for k, v in monthly_flow.items()
    ]
    trend_array = [{"month": k, "balance": v} for k, v in monthly_trend.items()]

    return {
        "summary": summary,
        "statement": statement_lines,
        "cash_flow": cash_flow_array,
        "balance_trend": trend_array
    }


def _build_snapshot_metrics(loan_doc: Any, dynamically_disbursed: float) -> Dict[str, Any]:
    """
    Compiles account metadata for the snapshot widget.
    """
    company_currency = frappe.get_cached_value("Company", loan_doc.company, "default_currency")
    
    lrs = DocType("Loan Repayment Schedule")
    schedule_summary = (
        frappe.qb.from_(lrs)
        .select(lrs.total_installments_paid, lrs.total_installments_raised)
        .where((lrs.loan == loan_doc.name) & (lrs.docstatus == 1))
        .orderby(lrs.creation, order=Order.desc)
        .limit(1)
        .run(as_dict=True)
    )
    emis_paid = f"{schedule_summary[0].total_installments_paid or 0} / {schedule_summary[0].total_installments_raised or 0}" if schedule_summary else "0 / 0"
    
    return {
        "currency": company_currency,
        "loan_account": loan_doc.name,
        "loan_product": loan_doc.loan_product,
        "loan_amount": flt(loan_doc.loan_amount),
        "disbursed_amount": dynamically_disbursed,
        "roi": flt(loan_doc.rate_of_interest),
        "emi_amount": flt(loan_doc.monthly_repayment_amount),
        "emi_start_date": loan_doc.repayment_start_date,
        "next_due_date": _get_next_due_date(loan_doc.name),
        "emis_paid": emis_paid
    }


def _calculate_aging_summary(loan_id: str) -> List[Dict[str, Any]]:
    """
    Cross-references total unallocated repayment volume against the active installment 
    schedule to calculate exact Days Past Due (DPD) buckets.
    """
    lr = DocType("Loan Repayment")
    total_paid_result = (
        frappe.qb.from_(lr)
        .select(Sum(lr.amount_paid))
        .where((lr.against_loan == loan_id) & (lr.docstatus == 1))
        .run()
    )
    unallocated_payment = flt(total_paid_result[0][0]) if total_paid_result and total_paid_result[0][0] else 0.0

    rs = DocType("Repayment Schedule")
    lrs = DocType("Loan Repayment Schedule")
    schedule = (
        frappe.qb.from_(rs)
        .join(lrs).on(rs.parent == lrs.name)
        .select(rs.payment_date, rs.total_payment)
        .where((lrs.loan == loan_id) & (lrs.docstatus == 1))
        .orderby(rs.payment_date, order=Order.asc)
        .run(as_dict=True)
    )

    buckets = {"Current": 0.0, "0-30 DPD": 0.0, "31-60 DPD": 0.0, "61-90 DPD": 0.0, "> 90 DPD": 0.0}
    today = getdate(nowdate())

    for inst in schedule:
        due = flt(inst.total_payment)
        if unallocated_payment >= due:
            unallocated_payment -= due
            continue
            
        unpaid_amount = due - unallocated_payment
        unallocated_payment = 0.0  # Funds exhausted
        
        dpd = (today - getdate(inst.payment_date)).days
        
        if dpd <= 0:
            buckets["Current"] += unpaid_amount
        elif dpd <= 30:
            buckets["0-30 DPD"] += unpaid_amount
        elif dpd <= 60:
            buckets["31-60 DPD"] += unpaid_amount
        elif dpd <= 90:
            buckets["61-90 DPD"] += unpaid_amount
        else:
            buckets["> 90 DPD"] += unpaid_amount

    total_unpaid = sum(buckets.values())
    
    formatted_aging = []
    for label, amount in buckets.items():
        percentage = round((amount / total_unpaid * 100), 2) if total_unpaid > 0 else 0.0
        formatted_aging.append({
            "label": label,
            "amount": amount,
            "percentage": percentage
        })

    return formatted_aging


def _get_next_due_date(loan_id: str):
    """Retrieves the immediate upcoming active schedule maturity."""
    try:
        rs = DocType("Repayment Schedule")
        lrs = DocType("Loan Repayment Schedule")
        query = (
            frappe.qb.from_(rs)
            .join(lrs).on(rs.parent == lrs.name)
            .select(rs.payment_date)
            .where((lrs.loan == loan_id) & (lrs.docstatus == 1) & (rs.payment_date >= nowdate()))
            .orderby(rs.payment_date, order=Order.asc)
            .limit(1)
        )
        result = query.run(as_dict=True)
        return result[0].payment_date if result else None
    except Exception:
        return None