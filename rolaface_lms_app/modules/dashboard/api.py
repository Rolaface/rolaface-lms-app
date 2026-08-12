import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from . import service


DASHBOARD_QUERY_PARAMS = """
      - in: query
        name: from_date
        schema: {type: string, format: date}
      - in: query
        name: to_date
        schema: {type: string, format: date}
      - in: query
        name: company
        schema: {type: string}
      - in: query
        name: branch
        schema: {type: string}
      - in: query
        name: loan_product
        schema: {type: string}
      - in: query
        name: customer
        schema: {type: string}
      - in: query
        name: status
        schema: {type: string}
"""


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_dashboard_summary():
    """
    Dashboard Summary
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Dashboard summary retrieved successfully.
    """
    try:
        data = service.get_dashboard_summary(frappe.local.form_dict)
        return send_response(status="success", message="Dashboard summary retrieved successfully.", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Dashboard Summary API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_dashboard_charts():
    """
    Dashboard Charts
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Dashboard charts retrieved successfully.
    """
    try:
        data = service.get_dashboard_charts(frappe.local.form_dict)
        return send_response(status="success", message="Dashboard charts retrieved successfully.", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Dashboard Charts API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_quick_insights():
    """
    Quick Insights
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Quick insights retrieved successfully.
    """
    try:
        data = service.get_quick_insights(frappe.local.form_dict)
        return send_response(status="success", message="Quick insights retrieved successfully.", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Quick Insights API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_pending_approvals(page=1, page_size=20):
    """
    Pending Approvals List
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Pending approvals retrieved successfully.
    """
    try:
        page, page_size = int(page), int(page_size)
        rows, total = service.get_pending_approvals(frappe.local.form_dict, page, page_size)

        response_data = {
            "success": True,
            "message": "Pending approvals retrieved successfully.",
            "data": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total,
                "has_prev": page > 1,
            },
        }
        return send_response_list(status="success", message="Success", data=response_data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Pending Approvals API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_overdue_tasks(page=1, page_size=20):
    """
    Overdue Collections Task List
    ---
    tags:
      - Dashboard
    responses:
      200:
        description: Overdue tasks retrieved successfully.
    """
    try:
        page, page_size = int(page), int(page_size)
        rows, total = service.get_overdue_tasks(frappe.local.form_dict, page, page_size)

        response_data = {
            "success": True,
            "message": "Overdue tasks retrieved successfully.",
            "data": rows,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": page * page_size < total,
                "has_prev": page > 1,
            },
        }
        return send_response_list(status="success", message="Success", data=response_data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Overdue Tasks API Error")