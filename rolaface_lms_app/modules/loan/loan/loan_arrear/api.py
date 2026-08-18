import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from . import service

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_arrear_summary(**kwargs):
    try:
        args = frappe.local.form_dict
        data = service.get_arrear_summary(args)
        return send_response(status="success", message="Summary retrieved", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Arrear Summary Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_arrear_charts(**kwargs):
    try:
        args = frappe.local.form_dict
        data = service.get_arrear_charts(args)
        return send_response(status="success", message="Charts retrieved", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Arrear Charts Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_arrear_insights(**kwargs):
    try:
        args = frappe.local.form_dict
        data = service.get_arrear_insights(args)
        return send_response(status="success", message="Insights retrieved", data=data, status_code=200, http_status=200)
    except Exception as e:
        return handle_api_error(e, "Get Arrear Insights Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_top_overdue_accounts(page=1, page_size=20, **kwargs):
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)
        rows, total = service.get_top_overdue_accounts(args, page, page_size)
        
        response_data = {
            "success": True,
            "message": "Overdue accounts retrieved",
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
        return handle_api_error(e, "Get Top Overdue Accounts Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def export_arrear_report(**kwargs):
    try:
        args = frappe.local.form_dict
        xlsx_data = service.export_arrear_report(args)
        
        frappe.local.response.filename = f"Arrear_Report_{frappe.utils.nowdate()}.xlsx"
        frappe.local.response.filecontent = xlsx_data
        frappe.local.response.type = "binary"
    except Exception as e:
        return handle_api_error(e, "Export Arrear Report Error")