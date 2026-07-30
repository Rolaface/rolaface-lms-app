import frappe
from . import service
from rolaface_lms_app.utils.api_response import send_response

@frappe.whitelist(allow_guest = False, methods=["POST"])
def create():
    data = frappe.local.form_dict
    try:
        payment = service.create_payment(data)

        return send_response(
                    status="success",
                    message="Payment created successfully",
                    status_code=201,
                    http_status=201
                )
    except Exception as e:
        frappe.log_error(str(e), "Create Purchase Invoice API Error")

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
