import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_loan_classification():
    """Create Unified Loan Classification Setup"""
    try:
        data = parse_api_payload()
        result_data = service.create_loan_classification(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Classification created successfully.",
            data=result_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Classification Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_loan_classification(id=None):
    """Update Unified Loan Classification Setup"""
    try:
        data = parse_api_payload()
        code = id or frappe.request.args.get("id")

        if not code:
            raise frappe.ValidationError("Classification Code (id) is required as a query parameter.")

        result_data = service.update_loan_classification(code, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Classification updated successfully.",
            data=result_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Classification Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_classification_by_id(id=None):
    """Get Unified Loan Classification Setup By ID (Code)"""
    try:
        code = id or frappe.request.args.get("id")
        if not code:
            raise frappe.ValidationError("Classification Code (id) is required.")

        data = service.get_loan_classification_by_id(code)
        
        return send_response(
            status="success",
            message="Loan Classification retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Classification Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_classifications(page=1, page_size=20):
    """List Unified Loan Classifications"""
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)
        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        records, total_records, total_pages = service.get_loan_classifications(
            args=args, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
        )

        response_data = {
            "success": True,
            "message": "Loan Classifications retrieved successfully.",
            "data": records,
            "pagination": {
                "page": page, "page_size": page_size,
                "total": total_records, "total_pages": total_pages,
                "has_next": page < total_pages, "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success", message="Success", data=response_data,
            status_code=200, http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get All Loan Classifications Error")


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_loan_classification(id=None):
    """Delete Unified Loan Classification Setup"""
    try:
        code = id or frappe.local.form_dict.get("id")
        if not code:
            raise frappe.ValidationError("Classification Code (id) is required.")

        service.delete_loan_classification(code)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Classification deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Loan Classification Error")