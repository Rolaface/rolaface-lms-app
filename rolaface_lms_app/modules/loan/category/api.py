import frappe
from . import service
from rolaface_lms_app.utils.api_response import send_response
from custom_api.utils.response import send_response, send_response_list

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_all(disabled=None, search=None, order_by="creation desc", page=1, page_size=10):
    try:
        categories = service.get_categories(disabled, search, order_by, page, page_size)
        return send_response_list(
                    status="success",
                    message="Success",
                    status_code=200,
                    data=categories,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"Internal Server Error: {str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get(name):
    try:
        category = service.get_category_by_name(name)
        return send_response(
                    status="success",
                    message="Success",
                    status_code=200,
                    data=category,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"Internal Server Error: {str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create():
    try:
        payload = frappe.local.form_dict
        category = service.create_category(payload)
        return send_response(
                    status="success",
                    message=f"Loan Category {category} successfully created.",
                    status_code=201,
                    http_status=201,
                )

    except Exception as e:
        return send_response(
                    status="error",
                    message=f"Internal Server Error: {str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update():
    try:
        payload = frappe.local.form_dict
        category = service.update_category(payload)
        return send_response(
                    status="success",
                    message=f"Loan Category successfully Updated.",
                    status_code=200,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def enable_disable():
    try:
        payload = frappe.local.form_dict
        category = service.enable_disable_category(payload)
        return send_response(
                    status="success",
                    message=f"Loan Category successfully Updated.",
                    status_code=200,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )