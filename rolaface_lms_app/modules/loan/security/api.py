import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_loan_security():
    """
    Create Loan Security
    ---
    tags:
      - Loan Security
    """
    try:
        data = parse_api_payload()
        security_data = service.create_loan_security(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security created successfully.",
            data=security_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Security API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_security(id=None):
    """
    Update Loan Security
    ---
    tags:
      - Loan Security
    """
    try:
        data = parse_api_payload()
        security_id = id or frappe.request.args.get("id")

        if not security_id:
            raise frappe.ValidationError("Loan Security ID is required as a query parameter (?id=...).")

        security_data = service.update_loan_security(security_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security updated successfully.",
            data=security_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Security API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_security_by_id(id=None):
    """
    Get Loan Security By ID
    ---
    tags:
      - Loan Security
    """
    try:
        security_id = id or frappe.request.args.get("id")
        
        if not security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        data = service.get_loan_security_by_id(security_id)
        
        return send_response(
            status="success",
            message="Loan Security retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Security By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_securities(page=1, page_size=20):
    """
    List Loan Securities
    ---
    tags:
      - Loan Security
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        securities, total, total_pages = service.get_loan_securities(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Securities retrieved successfully.",
            "data": securities,
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
        return handle_api_error(e, "Get All Loan Securities Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_loan_security(id=None):
    """
    Delete Loan Security
    ---
    tags:
      - Loan Security
    """
    try:
        security_id = id or frappe.local.form_dict.get("id")
        if not security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        service.delete_loan_security(security_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Loan Security Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def enable_loan_security(id=None):
    """
    Enable Loan Security
    ---
    tags:
      - Loan Security Status
    summary: Sets the disabled flag to 0.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Security enabled successfully.
    """
    try:
        security_id = id or frappe.request.args.get("id")
        if not security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        result = service.toggle_loan_security_status(security_id, disable_flag=0)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Enable Loan Security API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def disable_loan_security(id=None):
    """
    Disable Loan Security
    ---
    tags:
      - Loan Security Status
    summary: Sets the disabled flag to 1.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Security disabled successfully.
    """
    try:
        security_id = id or frappe.request.args.get("id")
        if not security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        result = service.toggle_loan_security_status(security_id, disable_flag=1)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Disable Loan Security API Error")