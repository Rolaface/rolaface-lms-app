import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_collateral():
    """
    Create Loan Security
    ---
    tags:
      - Loan Security
    summary: Create a new Loan Security entry.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - loan_security_code
              - loan_security_type
              - loan_security_name
            properties:
              loan_security_code:
                type: string
              loan_security_type:
                type: string
              loan_security_name:
                type: string
              loan_to_value_ratio:
                type: number
              haircut:
                type: number
              disabled:
                type: boolean
              original_security_value:
                type: number
    responses:
      201:
        description: Loan Security created successfully.
    """
    try:
        data = parse_api_payload()
        result = service.create_loan_security(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security created successfully.",
            data=result,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Security API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_collateral(id=None):
    """
    Update Loan Security
    ---
    tags:
      - Loan Security
    summary: Update specific attributes of a Loan Security.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Security updated successfully.
    """
    try:
        data = parse_api_payload()
        loan_security_id = id or frappe.request.args.get("id")

        if not loan_security_id:
            raise frappe.ValidationError("Loan Security ID is required as a query parameter (?id=...).")

        result = service.update_loan_security(loan_security_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Security updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Security API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_collateral_by_id(id=None):
    """
    Get Loan Security By ID
    ---
    tags:
      - Loan Security
    summary: Fetch full details of a Loan Security by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        loan_security_id = id or frappe.request.args.get("id")

        if not loan_security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        data = service.get_loan_security_by_id(loan_security_id)

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
def get_collateral(page=1, page_size=20):
    """
    List Loan Securities
    ---
    tags:
      - Loan Security
    summary: Paginated list of Loan Securities with advanced filtering.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        records, total_records, total_pages = service.get_loan_securities(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Securities retrieved successfully.",
            "data": records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
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
def delete_collateral(id=None):
    """
    Delete Loan Security
    ---
    tags:
      - Loan Security
    summary: Delete a Loan Security.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        loan_security_id = id or frappe.local.form_dict.get("id")
        if not loan_security_id:
            raise frappe.ValidationError("Loan Security ID is required.")

        service.delete_loan_security(loan_security_id)
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
def enable_collateral(id=None):
    """
    Enable Loan Security
    ---
    tags:
      - Loan Security
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
        loan_security_id = id or frappe.request.args.get("id")
        if not loan_security_id:
            raise frappe.ValidationError("Loan Security ID is required.")
 
        result = service.toggle_loan_security_status(loan_security_id, disable_flag=0)
        frappe.db.commit()
 
        return send_response(
            status="success",
            message="Loan Security has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Enable Loan Security API Error")
 
 
@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def disable_collateral(id=None):
    """
    Disable Loan Security
    ---
    tags:
      - Loan Security
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
        loan_security_id = id or frappe.request.args.get("id")
        if not loan_security_id:
            raise frappe.ValidationError("Loan Security ID is required.")
 
        result = service.toggle_loan_security_status(loan_security_id, disable_flag=1)
        frappe.db.commit()
 
        return send_response(
            status="success",
            message="Loan Security has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Disable Loan Security API Error")
 