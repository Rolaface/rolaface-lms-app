import frappe
from rolaface_lms_app.utils.api_response import (
    send_response,
    send_response_list,
    handle_api_error,
)
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_loan():
    """
    Create Loan
    ---
    tags:
      - Loan
    summary: Create a new Loan entry and associated Collaterals.
    """
    try:
        data = parse_api_payload()
        loan_data = service.create_loan(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan and Collaterals created successfully.",
            data=loan_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        return handle_api_error(e, "Create Loan API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan(id=None):
    try:
        data = parse_api_payload()
        loan_id = id or frappe.request.args.get("id")

        if not loan_id:
            raise frappe.ValidationError(
                "Loan ID is required as a query parameter (?id=...)."
            )

        loan_data = service.update_loan(loan_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan updated successfully.",
            data=loan_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Loan API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_by_id(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")

        data = service.get_loan_by_id(loan_id)

        return send_response(
            status="success",
            message="Loan retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loans(page=1, page_size=20):
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "name")
        sort_order = args.get("sort_order", "desc")

        loans, total_loans, total_pages = service.get_loans(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loans retrieved successfully.",
            "data": loans,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_loans,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success",
            message="Success",
            data=response_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get All Loans Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_loan(id=None):
    try:
        loan_id = id or frappe.local.form_dict.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")

        service.delete_loan(loan_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Loan Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_status(id=None, action=None):
    action_value = action or frappe.request.args.get("action")
    loan_id = id or frappe.request.args.get("id")

    try:
        if not loan_id:
            return send_response(
                status="fail",
                message="Loan ID is required",
                status_code=400,
                http_status=400,
            )

        if not action_value:
            return send_response(
                status="fail",
                message="Action is required (approved, cancelled, amend)",
                status_code=400,
                http_status=400,
            )

        action_clean = str(action_value).strip().lower()

        if action_clean not in {"approved", "cancelled", "amend"}:
            return send_response(
                status="fail",
                message=f"Invalid action '{action_clean}'. Allowed values: approved, cancelled, amend",
                status_code=400,
                http_status=400,
            )

        if not frappe.db.exists("Loan", loan_id):
            return send_response(
                status="fail",
                message=f"Loan '{loan_id}' not found",
                status_code=404,
                http_status=404,
            )

        result = service.update_loan_status(loan_id, action_clean)
        frappe.db.commit()

        action_map = {
            "approved": "approved",
            "cancelled": "cancelled",
            "amend": "amended",
        }

        return send_response(
            status="success",
            message=f"Loan {action_map[action_clean]} successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )

    except frappe.exceptions.ValidationError as e:
        frappe.db.rollback()
        return send_response(
            status="fail", message=str(e), status_code=400, http_status=400
        )

    except frappe.exceptions.PermissionError as e:
        frappe.db.rollback()
        return send_response(
            status="fail",
            message=f"Permission denied to {action_value} this Loan.",
            status_code=403,
            http_status=403,
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Loan Status API Error")
        return send_response(
            status="error",
            message="Internal Server Error",
            status_code=500,
            http_status=500,
        )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_schedule_by_id(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")

        data = service.get_repayment_schedule_by_id(loan_id)

        return send_response(
            status="success",
            message="Repayment schedule retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Repayment Schedule By ID Error")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def attach_loan_documents(id=None):
    try:
        data = parse_api_payload()
        loan_id = id or frappe.request.args.get("id")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required as a query parameter (?id=...).")

        documents = data.get("documents")
        loan_data = service.attach_loan_documents(loan_id, documents)

        return send_response(
            status="success",
            message="Documents attached successfully.",
            data=loan_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Attach Loan Documents API Error")