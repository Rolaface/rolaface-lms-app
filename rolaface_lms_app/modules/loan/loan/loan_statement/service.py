import frappe
from frappe.query_builder import DocType, Order
from frappe.query_builder.functions import Sum, Max
from frappe.utils import getdate, flt, nowdate, formatdate
from frappe.utils.pdf import get_pdf
from frappe.utils.xlsxutils import make_xlsx
from typing import Dict, Any, List, Tuple
from collections import defaultdict
from lending.loan_management.report.loan_statement_of_account.loan_statement_of_account import execute as get_loan_soa


def loan_statement_dashboard(loan_id: str, from_date: str = None, to_date: str = None, view_type: str = "detailed") -> Dict[str, Any]:
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    loan_doc = frappe.get_doc("Loan", loan_id)
    statement_lines = _get_native_statement_data(loan_doc, from_date, to_date, view_type)
    processed_data = _process_native_data(statement_lines)
    snapshot = _build_snapshot_metrics(loan_doc, processed_data["summary"]["total_disbursed"])
    aging_summary = _calculate_aging_summary(loan_id)

    return {
        "snapshot": snapshot,
        "summary": processed_data["summary"],
        "statement": statement_lines,
        "balance_trend": processed_data["balance_trend"],
        "cash_flow": processed_data["cash_flow"],
        "aging_summary": aging_summary
    }


def get_loan_statement(loan_id: str, from_date: str = None, to_date: str = None, page: int = 1, page_size: int = 20, search_term: str = None, view_type: str = "detailed", transaction_type: str = None, sort_by: str = "date", sort_order: str = "asc") -> Tuple[list, int, int]:
    if not frappe.db.exists("Loan", loan_id):
        raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

    loan_doc = frappe.get_doc("Loan", loan_id)
    statement_lines = _get_native_statement_data(loan_doc, from_date, to_date, view_type)

    if transaction_type:
        statement_lines = [line for line in statement_lines if line.get("transaction_type") == transaction_type]

    if search_term:
        search_term = search_term.lower()
        statement_lines = [
            line for line in statement_lines 
            if search_term in str(line.get("particulars", "")).lower() 
            or search_term in str(line.get("reference_no", "")).lower()
            or search_term in str(line.get("transaction_type", "")).lower()
        ]

    reverse_sort = str(sort_order).lower() == "desc"
    if sort_by == "date":
        statement_lines.sort(key=lambda x: (getdate(x["date"]) if x["date"] else getdate('1900-01-01'), x.get("reference_no", "")), reverse=reverse_sort)
    else:
        statement_lines.sort(key=lambda x: x.get(sort_by) if x.get(sort_by) is not None else "", reverse=reverse_sort)

    total_records = len(statement_lines)
    total_pages = (total_records + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    paginated_lines = statement_lines[start:end]

    return paginated_lines, total_records, total_pages


def generate_statement_excel(loan_id: str, from_date: str = None, to_date: str = None, view_type: str = "detailed") -> bytes:
    loan_doc = frappe.get_doc("Loan", loan_id)
    statement_lines = _get_native_statement_data(loan_doc, from_date, to_date, view_type)

    data = []
    data.append(["Date", "Transaction Type", "Transaction", "Loan", "Debit", "Credit", "Balance"])
    
    for line in statement_lines:
        data.append([
            formatdate(line["date"]) if line.get("date") else "",
            line.get("transaction_type", ""),
            line.get("reference_no", ""),
            loan_id,
            flt(line.get("debit", 0.0), 2),
            flt(line.get("credit", 0.0), 2),
            flt(line.get("balance", 0.0), 2)
        ])
        
    xlsx_file = make_xlsx(data, "Loan Statement")
    return xlsx_file.getvalue() if hasattr(xlsx_file, "getvalue") else xlsx_file


def generate_statement_pdf(loan_id: str, from_date: str = None, to_date: str = None, view_type: str = "detailed") -> bytes:
    loan_doc = frappe.get_doc("Loan", loan_id)
    statement_lines = _get_native_statement_data(loan_doc, from_date, to_date, view_type)
    
    html = f"""
    <style>
        body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10px; }}
        h2, h4 {{ text-align: center; margin: 5px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ border: 1px solid #d1d8dd; padding: 6px; text-align: left; }}
        th {{ background-color: #f3f3f3; }}
        .text-right {{ text-align: right; }}
    </style>
    <h2>Loan Statement</h2>
    <h4>Account: {loan_doc.name} | Product: {loan_doc.loan_product}</h4>
    <h4>Period: {formatdate(statement_lines[0]['date']) if statement_lines and statement_lines[0].get('date') else '-'} to {formatdate(statement_lines[-1]['date']) if statement_lines and statement_lines[-1].get('date') else '-'}</h4>
    
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Transaction Type</th>
                <th>Transaction</th>
                <th>Loan</th>
                <th class="text-right">Debit</th>
                <th class="text-right">Credit</th>
                <th class="text-right">Balance</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for line in statement_lines:
        html += f"""
            <tr>
                <td>{formatdate(line['date']) if line.get('date') else ''}</td>
                <td>{line.get('transaction_type', '')}</td>
                <td>{line.get('reference_no', '')}</td>
                <td>{loan_id}</td>
                <td class="text-right">{'{:,.2f}'.format(flt(line.get('debit', 0), 2))}</td>
                <td class="text-right">{'{:,.2f}'.format(flt(line.get('credit', 0), 2))}</td>
                <td class="text-right">{'{:,.2f}'.format(flt(line.get('balance', 0), 2))}</td>
            </tr>
        """
        
    html += """
        </tbody>
    </table>
    """
    
    return get_pdf(html)


def _get_native_statement_data(loan_doc: Any, from_date: str, to_date: str, view_type: str) -> List[Dict[str, Any]]:
    from_date_resolved = getdate(from_date) if from_date else loan_doc.repayment_start_date
    to_date_resolved = getdate(to_date) if to_date else getdate(nowdate())
    
    filters = frappe._dict({
        "company": loan_doc.company,
        "applicant_type": loan_doc.applicant_type,
        "applicant": loan_doc.applicant,
        "loan": loan_doc.name,
        "from_date": from_date_resolved,
        "to_date": to_date_resolved,
        # "group_by": "Grouped" if view_type == "summary" else "Detailed",
        "group_by": "Detailed",
    })
    
    columns, data = get_loan_soa(filters)
    formatted_data = []
    
    for row in data:
        if isinstance(row, dict):
            date_raw = row.get("posting_date") or row.get("date")
            t_type = row.get("transaction_type", "")
            
            if not date_raw and "Opening" in t_type:
                date_raw = from_date_resolved
                
            formatted_data.append({
                "date": getdate(date_raw) if date_raw else None,
                "particulars": t_type,
                "reference_no": row.get("transaction_name", "-"),
                "transaction_type": t_type,
                "debit": flt(row.get("debit", 0.0), 2),
                "credit": flt(row.get("credit", 0.0), 2),
                "balance": flt(row.get("balance", 0.0), 2)
            })
        else:
            date_raw = row[0] if len(row) > 0 else None
            t_type = row[1] if len(row) > 1 else ""
            
            if not date_raw and "Opening" in t_type:
                date_raw = from_date_resolved
                
            formatted_data.append({
                "date": getdate(date_raw) if date_raw else None,
                "particulars": t_type,
                "reference_no": row[2] if len(row) > 2 else "-",
                "transaction_type": t_type,
                "debit": flt(row[4], 2) if len(row) > 4 else 0.0,
                "credit": flt(row[5], 2) if len(row) > 5 else 0.0,
                "balance": flt(row[6], 2) if len(row) > 6 else 0.0
            })
            
    return formatted_data


def _process_native_data(statement_lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {"total_disbursed": 0.0, "total_repayments": 0.0, "total_charges": 0.0}
    monthly_flow = defaultdict(lambda: {"disbursal": 0.0, "repayment": 0.0, "charges": 0.0})
    monthly_trend = {}
    
    opening_balance = 0.0
    closing_balance = 0.0
    
    for txn in statement_lines:
        t_type = txn.get("transaction_type", "")
        
        if "Opening Balance" in t_type:
            opening_balance = txn.get("balance", 0.0)
            continue
            
        txn_date = txn.get("date")
        if not txn_date:
            continue
            
        month_key = formatdate(txn_date, "MMM 'yy")
        closing_balance = txn.get("balance", 0.0)
        monthly_trend[month_key] = closing_balance
        
        debit = txn.get("debit", 0.0)
        credit = txn.get("credit", 0.0)
        
        if "Disbursement" in t_type:
            summary["total_disbursed"] = flt(summary["total_disbursed"] + debit, 2)
            monthly_flow[month_key]["disbursal"] = flt(monthly_flow[month_key]["disbursal"] + debit, 2)
        elif "Repayment" in t_type:
            summary["total_repayments"] = flt(summary["total_repayments"] + credit, 2)
            monthly_flow[month_key]["repayment"] = flt(monthly_flow[month_key]["repayment"] + credit, 2)
        elif "Interest" in t_type or "Charge" in t_type or "Penalty" in t_type:
            summary["total_charges"] = flt(summary["total_charges"] + debit, 2)
            monthly_flow[month_key]["charges"] = flt(monthly_flow[month_key]["charges"] + debit, 2)

    summary["opening_balance"] = flt(opening_balance, 2)
    summary["closing_balance"] = flt(closing_balance, 2)
    
    cash_flow_array = [{"month": k, "disbursal": v["disbursal"], "repayment": v["repayment"], "charges": v["charges"]} for k, v in monthly_flow.items()]
    trend_array = [{"month": k, "balance": v} for k, v in monthly_trend.items()]
    
    return {
        "summary": summary,
        "cash_flow": cash_flow_array,
        "balance_trend": trend_array
    }

def _build_snapshot_metrics(loan_doc: Any, total_disbursed: float) -> Dict[str, Any]:
    company_currency = frappe.get_cached_value("Company", loan_doc.company, "default_currency")
    
    lrs = DocType("Loan Repayment Schedule")
    schedule_summary = (
        frappe.qb.from_(lrs)
        .select(
            lrs.name, 
            lrs.total_installments_paid, 
            lrs.total_installments_raised,
            lrs.monthly_repayment_amount
        )
        .where((lrs.loan == loan_doc.name) & (lrs.docstatus == 1))
        .orderby(lrs.creation, order=Order.desc)
        .limit(1)
        .run(as_dict=True)
    )
    
    emis_paid = f"{schedule_summary[0].total_installments_paid or 0} / {schedule_summary[0].total_installments_raised or 0}" if schedule_summary else "0 / 0"
    
    emi_amount = schedule_summary[0].monthly_repayment_amount if schedule_summary else 0.0
    
    return {
        "currency": company_currency, 
        "loan_account": loan_doc.name, 
        "loan_product": loan_doc.loan_product,
        "loan_amount": flt(loan_doc.loan_amount, 2), 
        "disbursed_amount": flt(total_disbursed, 2),
        "roi": flt(loan_doc.rate_of_interest, 2), 
        "emi_amount": flt(emi_amount, 2),
        "emi_start_date": loan_doc.repayment_start_date, 
        "next_due_date": _get_next_due_date(loan_doc.name),
        "emis_paid": emis_paid
    }


def _calculate_aging_summary(loan_id: str) -> List[Dict[str, Any]]:
    lr = DocType("Loan Repayment")
    total_paid_result = frappe.qb.from_(lr).select(Sum(lr.amount_paid)).where((lr.against_loan == loan_id) & (lr.docstatus == 1)).run()
    unallocated_payment = flt(total_paid_result[0][0], 2) if total_paid_result and total_paid_result[0][0] else 0.0

    rs = DocType("Repayment Schedule")
    lrs = DocType("Loan Repayment Schedule")
    schedule = frappe.qb.from_(rs).join(lrs).on(rs.parent == lrs.name).select(rs.payment_date, rs.total_payment).where((lrs.loan == loan_id) & (lrs.docstatus == 1)).orderby(rs.payment_date, order=Order.asc).run(as_dict=True)

    buckets = {"Current": 0.0, "0-30 DPD": 0.0, "31-60 DPD": 0.0, "61-90 DPD": 0.0, "> 90 DPD": 0.0}
    today = getdate(nowdate())

    for inst in schedule:
        due = flt(inst.total_payment, 2)
        if unallocated_payment >= due:
            unallocated_payment = flt(unallocated_payment - due, 2)
            continue
            
        unpaid_amount = flt(due - unallocated_payment, 2)
        unallocated_payment = 0.0
        dpd = (today - getdate(inst.payment_date)).days
        
        if dpd <= 0: buckets["Current"] = flt(buckets["Current"] + unpaid_amount, 2)
        elif dpd <= 30: buckets["0-30 DPD"] = flt(buckets["0-30 DPD"] + unpaid_amount, 2)
        elif dpd <= 60: buckets["31-60 DPD"] = flt(buckets["31-60 DPD"] + unpaid_amount, 2)
        elif dpd <= 90: buckets["61-90 DPD"] = flt(buckets["61-90 DPD"] + unpaid_amount, 2)
        else: buckets["> 90 DPD"] = flt(buckets["> 90 DPD"] + unpaid_amount, 2)

    total_unpaid = flt(sum(buckets.values()), 2)
    formatted_aging = []
    for label, amount in buckets.items():
        percentage = round((amount / total_unpaid * 100), 2) if total_unpaid > 0 else 0.0
        formatted_aging.append({"label": label, "amount": amount, "percentage": percentage})

    return formatted_aging


def _get_next_due_date(loan_id: str):
    try:
        rs = DocType("Repayment Schedule")
        lrs = DocType("Loan Repayment Schedule")
        query = frappe.qb.from_(rs).join(lrs).on(rs.parent == lrs.name).select(rs.payment_date).where((lrs.loan == loan_id) & (lrs.docstatus == 1) & (rs.payment_date >= nowdate())).orderby(rs.payment_date, order=Order.asc).limit(1)
        result = query.run(as_dict=True)
        return result[0].payment_date if result else None
    except Exception:
        return None