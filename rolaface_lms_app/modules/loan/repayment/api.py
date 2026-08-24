from rolaface_lms_app.utils.decorators import validate_payload
import frappe
from . import service
from rolaface_lms_app.utils.api_response import send_response

@frappe.whitelist(allow_guest = False, methods=["POST"])
@validate_payload("validate_payload") 
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

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_repayment_account(initiated_restructure=False):
    search_term = frappe.local.form_dict.get("search_term", "")
    limit = frappe.local.form_dict.get("limit", 20)

    try:
        results = service.get_loan_repayment_account(
            search_term=search_term, limit=int(limit), initiated_restructure=initiated_restructure
        )
        return send_response(
            status="success",
            message="Loan accounts fetched successfully",
            data=results,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Get Loan Repayment Account API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_by_id():
    repayment_id = frappe.request.args.get("id") 
    try:
        result = service.get_loan_repayment_by_id(repayment_id)
        return send_response(
            status="success",
            message="Loan repayment fetched successfully",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Get Loan Repayment By Id API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_all():
    args = frappe.local.form_dict
    page = int(args.get("page", 1))
    page_size = int(args.get("page_size", 20))
    sort_by = args.get("sort_by", "creation")
    sort_order = args.get("sort_order", "desc")

    try:
        repayments, total, total_pages = service.get_loan_repayments(
            args, page, page_size, sort_by, sort_order
        )
        return send_response(
            status="success",
            message="Loan repayments fetched successfully",
            data={
                "repayments": repayments,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Get Loan Repayments API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["PUT", "POST"])
def update():
    repayment_id = frappe.local.form_dict.get("id") or frappe.local.request.args.get("id")
    data = frappe.local.form_dict
    try:
        result = service.update_loan_repayment(repayment_id, data)
        return send_response(
            status="success",
            message="Loan repayment updated successfully",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Update Loan Repayment API Error")

        if db := getattr(frappe.local, "db", None):
            db.rollback(chain=True)
        else:
            frappe.db.rollback()

        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["DELETE", "POST"])
def delete():
    repayment_id = frappe.local.form_dict.get("id")
    try:
        service.delete_loan_repayment(repayment_id)
        return send_response(
            status="success",
            message="Loan repayment deleted successfully",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Delete Loan Repayment API Error")

        if db := getattr(frappe.local, "db", None):
            db.rollback(chain=True)
        else:
            frappe.db.rollback()

        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=False, methods=["POST"])
def update_status():
    repayment_id = frappe.local.form_dict.get("id")
    action = frappe.local.form_dict.get("action")
    try:
        result = service.update_loan_repayment_status(repayment_id, action)
        return send_response(
            status="success",
            message=f"Loan repayment status updated to '{action}'",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.log_error(str(e), "Update Loan Repayment Status API Error")

        if db := getattr(frappe.local, "db", None):
            db.rollback(chain=True)
        else:
            frappe.db.rollback()

        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )