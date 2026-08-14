import frappe
from .api_response import send_response, send_response_list
from frappe.desk.search import build_for_autosuggest, search_widget
from frappe.utils import flt


def _get_pagination_args():
    try:
        page = int(frappe.request.args.get("page", 1))
        page_size = int(frappe.request.args.get("page_size", 10))
    except ValueError:
        page, page_size = 1, 10
    return page, page_size


def _fetch_paginated_autosuggest(
    doctype,
    filters=None,
    search_fields=None,
    field_map=None,
    order_by="modified desc",
):
    txt = frappe.request.args.get("search", "").strip()
    page, page_size = _get_pagination_args()
    start = (page - 1) * page_size

    filters = filters or {}
    search_fields = search_fields or ["name"]

    or_filters = []
    if txt:
        for field in search_fields:
            or_filters.append([doctype, field, "like", f"%{txt}%"])

    required_fields = {"name"}
    if field_map:
        for value in field_map.values():
            if isinstance(value, str):
                required_fields.add(value)
            elif isinstance(value, (list, tuple)):
                required_fields.update(value)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        or_filters=or_filters if txt else None,
        fields=list(required_fields),
        limit_start=start,
        limit_page_length=page_size,
        order_by="modified desc",
    )

    def resolve(row, mapper):
        if callable(mapper):
            return mapper(row)
        if isinstance(mapper, str):
            return row.get(mapper)
        if isinstance(mapper, (list, tuple)):
            return " ".join(str(row.get(f) or "") for f in mapper).strip()
        return None

    response_data = []
    for row in rows:
        if field_map:
            item = {key: resolve(row, mapper) for key, mapper in field_map.items()}
        else:
            item = {
                "value": row.get("name"),
                "label": row.get("name"),
                "description": row.get("name"),
            }
        response_data.append(item)

    if txt and search_fields:
        count_result = frappe.get_all(
            doctype,
            filters=filters,
            or_filters=or_filters,
            fields=[{"COUNT": "name"}],
            as_list=True,
        )
        total_items = count_result[0][0] if count_result and count_result[0] else 0
    else:
        total_items = frappe.db.count(doctype, filters=filters)

    total_pages = (total_items + page_size - 1) // page_size if page_size else 1

    return {
        "data": response_data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "items_in_page": len(response_data),
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_customers():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Customer",
            filters=frappe._dict({}),
            search_fields=["name", "customer_name"],
            field_map={
                "value": "name",
                "label": "customer_name",
                "description": "name",
            },
        )
        return send_response_list("success", "Customers fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Customers API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_products():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Product",
            filters=frappe._dict({}),
            search_fields=["name", "product_name"],
            field_map={
                "value": "name",
                "label": "product_name",
                "description": "name",
            },
        )
        return send_response_list("success", "Loan Products fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Products API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_applications():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Application",
            filters=frappe._dict({"docstatus": 1}),
            search_fields=["name", "applicant", "applicant_name", "status"],
            field_map={
                "value": "name",
                "label": "applicant_name",
                "description": ["loan_product", "loan_amount", "status"],
            },
        )
        return send_response_list("success", "Loan Applications fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Applications API Error")
        return send_response("fail", str(e), None, 500, 500)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_currencies():
    try:
        txt = frappe.request.args.get("search", "").strip()
        
        try:
            page = int(frappe.request.args.get("page", 1))
            page_size = int(frappe.request.args.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10

        start = (page - 1) * page_size

        filters = {}
        if txt:
            filters = [
                ["Currency", "name", "like", f"%{txt}%"],
                ["Currency", "currency_name", "like", f"%{txt}%"]
            ]

        total_items = frappe.db.count("Currency", filters=filters)
        
        rows = frappe.get_all(
            "Currency",
            filters=filters,
            or_filters=filters if txt else None,
            fields=["name", "currency_name", "number_format", "symbol"],
            order_by="name asc",
            limit_start=start,
            limit_page_length=page_size
        )

        data = [
            {
                "name": row.name,
                "currency_name": row.currency_name,
                "symbol": row.symbol,
                "number_format": row.number_format,
            }
            for row in rows
        ]

        total_pages = (total_items + page_size - 1) // page_size if page_size else 1

        return send_response_list(
            status="success",
            message="Currencies fetched successfully.",
            data={
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "items_in_page": len(data),
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1,
                },
            },
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Currencies API Error")
        return send_response_list(
            status="fail",
            message=str(e),
            data=None,
            status_code=500,
            http_status=500,
        )

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loans():
    try:
        filters = {}

        status = frappe.form_dict.get("status")
        if status:
            if isinstance(status, str):
                status = frappe.parse_json(status)

            if isinstance(status, list) and status:
                filters["status"] = ["in", status]

        applicant = frappe.form_dict.get("applicant")
        if applicant:
            if isinstance(applicant, str):
                applicant = frappe.parse_json(applicant)

            if isinstance(applicant, list) and applicant:
                filters["applicant"] = ["in", applicant]

        data = _fetch_paginated_autosuggest(
            doctype="Loan",
            filters=filters,
            search_fields=[
                "name",
                "applicant",
                "applicant_name",
                "loan_product",
            ],
            field_map={
                "name": "name",
                "applicant": "applicant",
                "applicant_name": "applicant_name",
                "loan_product": "loan_product",
                "loan_amount": "loan_amount",
                "total_payment": "total_payment",
                "total_interest_payable": "total_interest_payable",
                "total_principal_paid": "total_principal_paid",
                "total_amount_paid": "total_amount_paid",
            },
            order_by="name asc",
        )

        for loan in data["data"]:
            loan["pending_principal_amount"] = (
                flt(loan.get("total_payment"))
                - flt(loan.get("total_interest_payable"))
                - flt(loan.get("total_principal_paid"))
            )

        return send_response_list(
            status="success",
            message="Loans fetched successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Get Loans API Error"
        )

        return send_response_list(
            status="fail",
            message="Internal Server Error",
            data=None,
            status_code=500,
            http_status=500,
        )

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_security_types():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Security Type",
            filters=frappe._dict({}),
            search_fields=["name", "loan_security_type"],
            field_map={
                "value": "name",
                "label": "loan_security_type",
                "description": "loan_security_type",
            },
        )
        return send_response_list("success", "Loan Security Types fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Security Types API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_category():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Category",
            filters=frappe._dict({}),
            search_fields=["name", "loan_category_code", "loan_category_name"],
            field_map={
                "value": "loan_category_code",
                "label": "loan_category_name",
                "description": "loan_category_name",
            },
        )
        return send_response_list("success", "Loan Category fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Category API Error")
        return send_response("fail", str(e), None, 500, 500)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_securities():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Security",
            filters=frappe._dict({}),
            search_fields=["name", "loan_security_name", "loan_security_code"],
            field_map={
                "value": "name",
                "label": "loan_security_name",
                "description": "loan_security_type",
            },
        )
        return send_response_list("success", "Loan Securities fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Securities API Error")
        return send_response("fail", str(e), None, 500, 500)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_disbursements():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Disbursement",
            filters=frappe._dict({"docstatus": 1}),
            search_fields=["name", "loan", "applicant"],
            field_map={
                "value": "name",
                "label": "name",
                "description": ["loan", "disbursed_amount"],
            },
        )
        return send_response_list("success", "Loan Disbursements fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Disbursements API Error")
        return send_response("fail", str(e), None, 500, 500)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_repayments():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Repayment",
            filters=frappe._dict({"docstatus": 1}),
            search_fields=["name", "loan", "applicant"],
            field_map={
                "value": "name",
                "label": "name",
                "description": ["loan", "amount_paid"],
            },
        )
        return send_response_list("success", "Loan Repayments fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Repayments API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_partners():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Partner",
            filters=frappe._dict({}),
            search_fields=["name", "partner_name"],
            field_map={
                "value": "name",
                "label": "partner_name",
                "description": "name",
            },
        )
        return send_response_list("success", "Loan Partners fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Partners API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_demand_offset_orders():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Loan Demand Offset Order",
            filters=frappe._dict({}),
            search_fields=["name"],
            field_map={
                "value": "name",
                "label": "name",
                "description": "name",
            },
        )
        return send_response_list("success", "Loan Demand Offset Orders fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loan Demand Offset Order API Error")
        return send_response("fail", str(e), None, 500, 500)

def _get_account_filters():
    filters = {}

    root_type = frappe.request.args.get("root_type")
    if root_type:
        values = [v.strip() for v in root_type.split(",") if v.strip()]
        filters["root_type"] = ["in", values] if len(values) > 1 else values[0]

    is_group = frappe.request.args.get("is_group")
    if is_group is not None and is_group != "":
        filters["is_group"] = is_group

    return filters


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_accounts():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Account",
            filters=_get_account_filters(),
            search_fields=["name"],
            field_map={
                "value": "name",
                "label": "account_name",
                "description": "account_name",
            },
        )
        return send_response_list("success", "Accounts fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Accounts API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_items():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Item",
            filters=frappe._dict({}),
            search_fields=["name"],
            field_map={
                "value": "name",
                "label": "name",
                "description": "name",
            },
        )
        return send_response_list("success", "Items fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Items API Error")
        return send_response("fail", str(e), None, 500, 500)