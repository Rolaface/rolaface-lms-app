import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_loan_disbursement():
    """
    Create Loan Disbursement
    ---
    tags:
      - Loan Disbursement
    summary: Create a new Loan Disbursement entry.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - against_loan
              - disbursed_amount
            properties:
              against_loan:
                type: string
              disbursed_amount:
                type: number
              company:
                type: string
              disbursement_charges:
                type: array
                items:
                  type: object
                  properties:
                    charge:
                      type: string
                    amount:
                      type: number
                    account:
                      type: string
                    treatment_of_charge:
                      type: string
                      enum: ["Billed Separately", "Add to first repayment"]
    responses:
      201:
        description: Loan Disbursement created successfully.
    """
    try:
        data = parse_api_payload()
        disbursement_data = service.create_loan_disbursement(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Disbursement created successfully.",
            data=disbursement_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Disbursement API Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_loan_disbursement(id=None):
    """
    Update Loan Disbursement
    ---
    tags:
      - Loan Disbursement
    summary: Update specific attributes of a Loan Disbursement.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Disbursement updated successfully.
    """
    try:
        data = parse_api_payload()
        disbursement_id = id or frappe.request.args.get("id")

        if not disbursement_id:
            raise frappe.ValidationError("Loan Disbursement ID is required as a query parameter (?id=...).")

        disbursement_data = service.update_loan_disbursement(disbursement_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Disbursement updated successfully.",
            data=disbursement_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Disbursement API Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_disbursement_by_id(id=None):
    """
    Get Loan Disbursement By ID
    ---
    tags:
      - Loan Disbursement
    summary: Fetch full details of a Loan Disbursement by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        disbursement_id = id or frappe.request.args.get("id")
        
        if not disbursement_id:
            raise frappe.ValidationError("Loan Disbursement ID is required.")

        data = service.get_loan_disbursement_by_id(disbursement_id)
        
        return send_response(
            status="success",
            message="Loan Disbursement retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Disbursement By ID Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_disbursements(page=1, page_size=20):
    """
    List Loan Disbursements
    ---
    tags:
      - Loan Disbursement
    summary: Paginated list of Loan Disbursements with advanced filtering.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        disbursements, total_disbursements, total_pages = service.get_loan_disbursements(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Disbursements retrieved successfully.",
            "data": disbursements,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_disbursements,
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
        return handle_api_error(e, "Get All Loan Disbursements Error")


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_loan_disbursement(id=None):
    """
    Delete Loan Disbursement
    ---
    tags:
      - Loan Disbursement
    summary: Delete a Draft Loan Disbursement.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        disbursement_id = id or frappe.local.form_dict.get("id")
        if not disbursement_id:
            raise frappe.ValidationError("Loan Disbursement ID is required.")

        service.delete_loan_disbursement(disbursement_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Disbursement deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Loan Disbursement Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_loan_disbursement_status(id=None, action=None):
    """
    Update Loan Disbursement Status (Submit/Approve, Cancel, Amend)
    ---
    tags:
      - Loan Disbursement
    summary: Updates the status lifecycle of a Loan Disbursement.
    """
    action_value = action or frappe.request.args.get("action")
    disbursement_id = id or frappe.request.args.get("id")
    
    try:
        if not disbursement_id:
            return send_response(
                status="fail",
                message="Loan Disbursement ID is required",
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

        if not frappe.db.exists("Loan Disbursement", disbursement_id):
            return send_response(
                status="fail",
                message=f"Loan Disbursement '{disbursement_id}' not found",
                status_code=404,
                http_status=404,
            )

        result = service.update_loan_disbursement_status(disbursement_id, action_clean)
        frappe.db.commit()

        action_map = {"approved": "approved", "cancelled": "cancelled", "amend": "amended"}

        return send_response(
            status="success",
            message=f"Loan Disbursement {action_map[action_clean]} successfully.",
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
            message=f"You do not have permission to {action_value} the status of this Loan Disbursement. Please contact your Administrator.", 
            status_code=403, 
            http_status=403
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Loan Disbursement Status API Error")
        return send_response(
            status="error",
            message="Internal Server Error",
            status_code=500,
            http_status=500,
        )