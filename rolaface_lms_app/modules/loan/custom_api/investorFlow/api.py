import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_investor_flow():
    """
    Create Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Create a new Investor Flow (investor, product and investment terms).
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investor
              - investment_product
              - investment_amount
              - repayment_frequency
              - maturity_date
              - interest_rate
              - first_repayment_date
            properties:
              investor:
                type: string
                description: Customer ID.
              investment_product:
                type: string
                description: Custom Investment Product ID.
              investment_amount:
                type: integer
              repayment_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              maturity_date:
                type: string
                format: date
              interest_rate:
                type: number
              first_repayment_date:
                type: string
                format: date
              penalty_rate:
                type: number
    responses:
      201:
        description: Investor Flow created successfully.
    """
    try:
        data = parse_api_payload()
        result = service.create_investor_flow(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow created successfully.",
            data=result,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Investor Flow API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_flow(id=None):
    """
    Update Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Update specific attributes of an Investor Flow.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Investor Flow updated successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required as a query parameter (?id=...).")

        result = service.update_investor_flow(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Flow API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_flow_by_id(id=None):
    """
    Get Investor Flow By ID
    ---
    tags:
      - Investor Flow
    summary: Fetch full details of an Investor Flow by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        data = service.get_investor_flow_by_id(investor_flow_id)

        return send_response(
            status="success",
            message="Investor Flow retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Flow By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_flow(page=1, page_size=20):
    """
    List Investor Flows
    ---
    tags:
      - Investor Flow
    summary: Paginated list of Investor Flows with filtering.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID, investor (Customer ID) or investment product ID.
      - in: query
        name: investor
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: investment_product
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: repayment_frequency
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: status
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: sort_by
        schema:
          type: string
      - in: query
        name: sort_order
        schema:
          type: string
          enum: [asc, desc]
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        records, total_records, total_pages = service.get_investor_flows(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Investor Flows retrieved successfully.",
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
        return handle_api_error(e, "Get All Investor Flows Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_investor_flow(id=None):
    """
    Delete Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Delete an Investor Flow.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        investor_flow_id = id or frappe.local.form_dict.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        service.delete_investor_flow(investor_flow_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Investor Flow Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_flow_status(id=None, action=None):
    """
    Update Investor Flow Status
    ---
    tags:
      - Investor Flow
    summary: Move an Investor Flow to a new status.
    description: |
      Allowed transitions: Draft -> Approved / Cancelled, Approved -> Received / Cancelled.
      Received and Cancelled are final.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
      - in: query
        name: action
        required: true
        schema:
          type: string
          enum: [approved, received, cancelled]
    responses:
      200:
        description: Investor Flow status updated successfully.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        action_value = action or frappe.request.args.get("action")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        if not action_value:
            raise frappe.ValidationError("Action is required (approved, received, cancelled).")

        action_clean = str(action_value).strip().lower()

        result = service.update_investor_flow_status(investor_flow_id, action_clean)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Investor Flow {result['status']} successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Flow Status API Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_schedules():
    """
    Get Investor Flow Schedule
    ---
    tags:
      - Investor Flow
    summary: Calculate the payout schedule for the given terms. Nothing is saved.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investment_amount
              - repayment_frequency
              - maturity_date
              - interest_rate
              - first_repayment_date
            properties:
              investment_amount:
                type: integer
              repayment_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              maturity_date:
                type: string
                format: date
              interest_rate:
                type: number
              first_repayment_date:
                type: string
                format: date
              penalty_rate:
                type: number
    responses:
      200:
        description: Schedule calculated successfully.
    """
    try:
        data = parse_api_payload()
        result = service.get_schedule(data)

        return send_response(
            status="success",
            message="Schedule calculated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Flow Schedule Error")