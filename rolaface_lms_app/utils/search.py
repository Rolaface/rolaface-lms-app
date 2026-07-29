import frappe
from custom_hrms.utils.response import send_response, send_response_list
from frappe.desk.search import build_for_autosuggest, search_widget


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

@frappe.whitelist(allow_guest=False, methods=["GET"])
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


@frappe.whitelist(allow_guest=False, methods=["GET"])
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


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_accounts():
    try:
        data = _fetch_paginated_autosuggest(
            doctype="Account",
            filters=_get_account_filters(),
            search_fields=["name"],
            field_map={
                "value": "name",
                "label": "name",
                "description": "name",
            },
        )
        return send_response_list("success", "Accounts fetched successfully.", data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Accounts API Error")
        return send_response("fail", str(e), None, 500, 500)

@frappe.whitelist(allow_guest=False, methods=["GET"])
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