import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_loan_security_type():
    """
    Create Loan Security Type
    ---
    tags:
      - Loan Security Type
    """
    try:
        data = parse_api_payload()
        type_data = service.create_loan_security_type(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security Type created successfully.",
            data=type_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Security Type API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_security_type(id=None):
    """
    Update Loan Security Type
    ---
    tags:
      - Loan Security Type
    """
    try:
        data = parse_api_payload()
        type_id = id or frappe.request.args.get("id")

        if not type_id:
            raise frappe.ValidationError("Loan Security Type ID is required as a query parameter (?id=...).")

        type_data = service.update_loan_security_type(type_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security Type updated successfully.",
            data=type_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Security Type API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_security_type_by_id(id=None):
    """
    Get Loan Security Type By ID
    ---
    tags:
      - Loan Security Type
    """
    try:
        type_id = id or frappe.request.args.get("id")
        
        if not type_id:
            raise frappe.ValidationError("Loan Security Type ID is required.")

        data = service.get_loan_security_type_by_id(type_id)
        
        return send_response(
            status="success",
            message="Loan Security Type retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Security Type By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_security_types(page=1, page_size=20):
    """
    List Loan Security Types
    ---
    tags:
      - Loan Security Type
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        types, total, total_pages = service.get_loan_security_types(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Security Types retrieved successfully.",
            "data": types,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
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
        return handle_api_error(e, "Get All Loan Security Types Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_loan_security_type(id=None):
    """
    Delete Loan Security Type
    ---
    tags:
      - Loan Security Type
    """
    try:
        type_id = id or frappe.local.form_dict.get("id")
        if not type_id:
            raise frappe.ValidationError("Loan Security Type ID is required.")

        service.delete_loan_security_type(type_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security Type deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Loan Security Type Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def enable_loan_security_type(id=None):
    """
    Enable Loan Security Type
    ---
    tags:
      - Loan Security Type Status
    summary: Sets the disabled flag to 0.
    """
    try:
        type_id = id or frappe.request.args.get("id")
        if not type_id:
            raise frappe.ValidationError("Loan Security Type ID is required.")

        result = service.toggle_loan_security_type_status(type_id, disable_flag=0)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security Type has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Enable Loan Security Type API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def disable_loan_security_type(id=None):
    """
    Disable Loan Security Type
    ---
    tags:
      - Loan Security Type Status
    summary: Sets the disabled flag to 1.
    """
    try:
        type_id = id or frappe.request.args.get("id")
        if not type_id:
            raise frappe.ValidationError("Loan Security Type ID is required.")

        result = service.toggle_loan_security_type_status(type_id, disable_flag=1)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security Type has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Disable Loan Security Type API Error")