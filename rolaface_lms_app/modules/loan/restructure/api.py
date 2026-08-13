from rolaface_lms_app.utils.decorators import validate_payload
import frappe
from . import service
from rolaface_lms_app.utils.api_response import send_response

@frappe.whitelist(allow_guest = False, methods=["POST"])
@validate_payload("validate_payload") 
def create():
    data = frappe.local.form_dict
    try:
        restructure = service.create_restructure(data)

        return send_response(
                    status="success",
                    message="Restructure created successfully",
                    status_code=201,
                    http_status=201
                )

    except Exception as e:
        frappe.log_error(str(e), "Create Loan Restructure API Error")

        if db := getattr(frappe.local, "db", None):
            db.rollback(chain=True)
        else:
            frappe.db.rollback()

        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest = False, methods=["PUT"])
@validate_payload("validate_update_payload") 
def update():
    data = frappe.local.form_dict
    try:
        restructure = service.update_restructure(data)

        return send_response(
                    status="success",
                    message="Restructure updated successfully",
                    status_code=201,
                    http_status=201
                )
    except Exception as e:
        frappe.log_error(str(e), "Update Loan Restructure API Error")

        if db := getattr(frappe.local, "db", None):
            db.rollback(chain=True)
        else:
            frappe.db.rollback()

        return send_response(
                                status="fail",
                                message=str(e),
                                status_code=500,
                                http_status=500
                            )

@frappe.whitelist(allow_guest=False, methods=["GET"])
@validate_payload("validate_get_by_id") 
def get(name):
    try:
        result = service.get_by_name(name)
        return send_response(
            status="success",
            message="Loan Restructure fetched successfully",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Get Loan Restructure By Name API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_all(search=None, order_by="creation desc", page=1, page_size=10):
    try:
        result = service.get_restructures(search, order_by, page, page_size)
        return send_response(
            status="success",
            message="Loan Restructure fetched successfully",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Get Loan Restructure By Name API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )
