import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import getdate, nowdate, flt
from .constant import FILTER_FIELD_MAP, DOCTYPE_FILTER_FIELDS


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
    import datetime
    return datetime.date(int(year), int(month), 1).strftime("%b %y")