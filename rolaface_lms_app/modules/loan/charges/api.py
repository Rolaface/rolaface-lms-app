import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_charge():
    """
    Create Charge Setup (Item)
    ---
    tags:
      - Charges Setup
    summary: Create a new Charge Item setup.
    """
    try:
        data = parse_api_payload()
        charge_data = service.create_charge(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Charge created successfully.",
            data=charge_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Charge API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_charge(id=None):
    """
    Update Charge Setup (Item)
    ---
    tags:
      - Charges Setup
    summary: Update specific attributes of a Charge Item setup.
    """
    try:
        data = parse_api_payload()
        charge_id = id or frappe.request.args.get("id")

        if not charge_id:
            raise frappe.ValidationError("Charge ID is required as a query parameter (?id=...).")

        charge_data = service.update_charge(charge_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Charge updated successfully.",
            data=charge_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Charge API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_charge_by_id(id=None):
    """
    Get Charge By ID
    ---
    tags:
      - Charges Setup
    summary: Fetch details of a Charge Item by ID.
    """
    try:
        charge_id = id or frappe.request.args.get("id")
        
        if not charge_id:
            raise frappe.ValidationError("Charge ID is required.")

        data = service.get_charge_by_id(charge_id)
        
        return send_response(
            status="success",
            message="Charge retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Charge By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_charges(page=1, page_size=20):
    """
    List Charges
    ---
    tags:
      - Charges Setup
    summary: Paginated list of Charges Setup (Items).
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        charges, total_charges, total_pages = service.get_charges(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Charges retrieved successfully.",
            "data": charges,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_charges,
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
        return handle_api_error(e, "Get All Charges Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_charge(id=None):
    """
    Delete Charge Setup
    ---
    tags:
      - Charges Setup
    summary: Delete a Charge Item setup.
    """
    try:
        charge_id = id or frappe.local.form_dict.get("id")
        if not charge_id:
            raise frappe.ValidationError("Charge ID is required.")

        service.delete_charge(charge_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Charge deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Charge Error")

@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def enable_charge(id=None):
    """
    Enable Charge Setup
    ---
    tags:
      - Charges Setup
    summary: Sets the disabled flag to 0 for a Charge Item.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Charge enabled successfully.
    """
    try:
        charge_id = id or frappe.request.args.get("id")
        if not charge_id:
            raise frappe.ValidationError("Charge ID is required.")

        result = service.toggle_charge_status(charge_id, disable_flag=0)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Charge has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Enable Charge API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def disable_charge(id=None):
    """
    Disable Charge Setup
    ---
    tags:
      - Charges Setup
    summary: Sets the disabled flag to 1 for a Charge Item.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Charge disabled successfully.
    """
    try:
        charge_id = id or frappe.request.args.get("id")
        if not charge_id:
            raise frappe.ValidationError("Charge ID is required.")

        result = service.toggle_charge_status(charge_id, disable_flag=1)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Charge has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Disable Charge API Error")