import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import getdate, nowdate, flt
import datetime

FILTER_FIELD_MAP = {
    "company": "company",
    "branch": "branch",
    "loan_product": "loan_product",
    "customer": "applicant",
    "status": "status",
}

DOCTYPE_FILTER_FIELDS = {
    "Loan": {"company", "branch", "loan_product", "applicant", "status"},
    "Custom Loan Application": {"company", "application_type", "customer", "status"},
    "Loan Disbursement": {"company", "branch", "loan_product", "applicant", "status"},
    "Loan Repayment": {"company", "branch", "loan_product", "applicant"},
    "Loan Demand": {"company", "branch", "loan_product", "applicant"},
}

PENDING_APPROVAL_STATUSES = ["Draft", "Under Review", "Pending Approval", "Manager Approval"]

PAR_BUCKETS = [
    {"label": "30 Days", "min_days": 1, "max_days": 30},
    {"label": "60 Days", "min_days": 31, "max_days": 60},
    {"label": "90+ Days", "min_days": 61, "max_days": None},
]

RISK_GRADE_BUCKETS = [
    {"label": "Low Risk", "min_days": 0, "max_days": 30},
    {"label": "Medium Risk", "min_days": 31, "max_days": 60},
    {"label": "High Risk", "min_days": 61, "max_days": None},
]

def parse_dashboard_filters(args):
    from_date = args.get("from_date")
    to_date = args.get("to_date")
    from_date = getdate(from_date) if from_date else None
    to_date = getdate(to_date) if to_date else getdate(nowdate())
    
    if from_date and from_date > to_date:
        raise frappe.ValidationError("from_date cannot be after to_date.")
        
    filters = {}
    for query_param, doc_field in FILTER_FIELD_MAP.items():
        value = args.get(query_param)
        if value:
            filters[doc_field] = value
            
    return {"from_date": from_date, "to_date": to_date, "filters": filters}

def filter_subset(doctype, filters):
    allowed_fields = DOCTYPE_FILTER_FIELDS.get(doctype, set())
    return {field: value for field, value in filters.items() if field in allowed_fields}

def date_range_filter(from_date, to_date):
    return ["<=", to_date] if from_date is None else ["between", [from_date, to_date]]

def apply_filters(query, doc, filters):
    for fieldname, value in filters.items():
        if isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], str):
            operator, operand = value[0].lower(), value[1]
            if operator == "in":
                query = query.where(doc[fieldname].isin(operand))
            elif operator == "not in":
                query = query.where(doc[fieldname].notin(operand))
            elif operator == "between":
                query = query.where(doc[fieldname].between(operand[0], operand[1]))
            elif operator == ">=":
                query = query.where(doc[fieldname] >= operand)
            elif operator == "<=":
                query = query.where(doc[fieldname] <= operand)
            elif operator == ">":
                query = query.where(doc[fieldname] > operand)
            elif operator == "<":
                query = query.where(doc[fieldname] < operand)
            elif operator == "!=":
                query = query.where(doc[fieldname] != operand)
        else:
            query = query.where(doc[fieldname] == value)
    return query

def fetch_sum_totals(doctype, sum_fields, date_field, from_date, to_date, filters):
    doc = frappe.qb.DocType(doctype)
    query = frappe.qb.from_(doc)
    
    for field in sum_fields:
        query = query.select(Sum(doc[field]).as_(field))
        
    if from_date is None:
        query = query.where(doc[date_field] <= to_date)
    else:
        query = query.where(doc[date_field].between(from_date, to_date))
        
    query = apply_filters(query, doc, filters)
    result = query.run(as_dict=True)
    row = result[0] if result else {}
    
    return {field: flt(row.get(field)) for field in sum_fields}

def month_label(year, month):
    return datetime.date(int(year), int(month), 1).strftime("%b %y")

def get_company_loan_classifications(company: str):
    ranges = frappe.get_all(
        "Loan Classification Range", 
        filters={"parent": company}, 
        fields=["classification_code", "classification_name", "min_dpd_range", "max_dpd_range"]
    )
    
    provisions = frappe.get_all(
        "Loan IRAC Provisioning Configuration", 
        filters={"parent": company}, 
        fields=["classification_code", "provision_rate"]
    )
    
    prov_map = {p.classification_code: flt(p.provision_rate) for p in provisions}
    
    buckets = []
    for r in ranges:
        buckets.append({
            "code": r.classification_code,
            "name": r.classification_name,
            "min_dpd": flt(r.min_dpd_range),
            "max_dpd": flt(r.max_dpd_range) if flt(r.max_dpd_range) > 0 else float('inf'),
            "provision_rate": prov_map.get(r.classification_code, 0.0),
            "amount": 0.0,
            "provision_amount": 0.0
        })
        
    # Sort by minimum DPD to ensure chronological evaluation
    buckets.sort(key=lambda x: x["min_dpd"])
    return buckets