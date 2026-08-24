import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from . import service

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_dashboard_summary(from_date=None, to_date=None, **kwargs):
    try:
        args = frappe.local.form_dict
        args.update({"from_date": from_date, "to_date": to_date})
        data = service.get_dashboard_summary(args)
        return send_response(status="success", message="Success", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_dashboard_charts(from_date=None, to_date=None, **kwargs):
    try:
        args = frappe.local.form_dict
        args.update({"from_date": from_date, "to_date": to_date})
        data = service.get_dashboard_charts(args)
        return send_response(status="success", message="Success", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_quick_insights(from_date=None, to_date=None, **kwargs):
    try:
        args = frappe.local.form_dict
        args.update({"from_date": from_date, "to_date": to_date})
        data = service.get_quick_insights(args)
        return send_response(status="success", message="Success", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_pending_approvals(from_date=None, to_date=None, page=1, page_size=5, **kwargs):
    try:
        args = frappe.local.form_dict
        args.update({"from_date": from_date, "to_date": to_date})
        page, page_size = int(page), int(page_size)
        rows, total = service.get_pending_approvals(args, page, page_size)
        
        response_data = {
            "success": True,
            "message": "Success",
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
        return handle_api_error(e, "Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_overdue_tasks(from_date=None, to_date=None, page=1, page_size=5, **kwargs):
    try:
        args = frappe.local.form_dict
        args.update({"from_date": from_date, "to_date": to_date})
        page, page_size = int(page), int(page_size)
        rows, total = service.get_overdue_tasks(args, page, page_size)
        
        response_data = {
            "success": True,
            "message": "Success",
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
        return handle_api_error(e, "Error")