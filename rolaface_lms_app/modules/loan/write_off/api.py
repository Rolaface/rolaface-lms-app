import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_loan_write_off():
    """
    Create Loan Write Off
    ---
    tags:
      - Loan Write Off
    summary: Create a new Loan Write Off entry.
    """
    try:
        data = parse_api_payload()
        write_off_data = service.create_loan_write_off(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Write Off created successfully.",
            data=write_off_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Loan Write Off API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_write_off(id=None):
    """
    Update Loan Write Off
    ---
    tags:
      - Loan Write Off
    summary: Update specific attributes of a Loan Write Off.
    """
    try:
        data = parse_api_payload()
        write_off_id = id or frappe.request.args.get("id")

        if not write_off_id:
            raise frappe.ValidationError("Loan Write Off ID is required as a query parameter (?id=...).")

        write_off_data = service.update_loan_write_off(write_off_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Write Off updated successfully.",
            data=write_off_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Loan Write Off API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_write_off_by_id(id=None):
    """
    Get Loan Write Off By ID
    ---
    tags:
      - Loan Write Off
    summary: Fetch full details of a Loan Write Off by ID.
    """
    try:
        write_off_id = id or frappe.request.args.get("id")
        
        if not write_off_id:
            raise frappe.ValidationError("Loan Write Off ID is required.")

        data = service.get_loan_write_off_by_id(write_off_id)
        
        return send_response(
            status="success",
            message="Loan Write Off retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Write Off By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_write_offs(page=1, page_size=20):
    """
    List Loan Write Offs
    ---
    tags:
      - Loan Write Off
    summary: Paginated list of Loan Write Offs with advanced filtering.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        write_offs, total_records, total_pages = service.get_loan_write_offs(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Write Offs retrieved successfully.",
            "data": write_offs,
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
        return handle_api_error(e, "Get All Loan Write Offs Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_loan_write_off(id=None):
    """
    Delete Loan Write Off
    ---
    tags:
      - Loan Write Off
    summary: Delete a Draft Loan Write Off.
    """
    try:
        write_off_id = id or frappe.local.form_dict.get("id")
        if not write_off_id:
            raise frappe.ValidationError("Loan Write Off ID is required.")

        service.delete_loan_write_off(write_off_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Write Off deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Loan Write Off Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_write_off_status(id=None, action=None):
    """
    Update Loan Write Off Status (Submit/Approve, Cancel, Amend)
    ---
    tags:
      - Loan Write Off
    summary: Updates the status lifecycle of a Loan Write Off.
    """
    action_value = action or frappe.request.args.get("action")
    write_off_id = id or frappe.request.args.get("id")
    
    try:
        if not write_off_id:
            return send_response(
                status="fail",
                message="Loan Write Off ID is required",
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

        if not frappe.db.exists("Loan Write Off", write_off_id):
            return send_response(
                status="fail",
                message=f"Loan Write Off '{write_off_id}' not found",
                status_code=404,
                http_status=404,
            )

        result = service.update_loan_write_off_status(write_off_id, action_clean)
        frappe.db.commit()

        action_map = {"approved": "approved", "cancelled": "cancelled", "amend": "amended"}

        return send_response(
            status="success",
            message=f"Loan Write Off {action_map[action_clean]} successfully.",
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
            message=f"You do not have permission to {action_value} this Loan Write Off. Please contact your Administrator.", 
            status_code=403, 
            http_status=403
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Loan Write Off Status API Error")
        return send_response(
            status="error",
            message="Internal Server Error",
            status_code=500,
            http_status=500,
        )