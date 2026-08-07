import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error, send_response_list
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_loan_application():
    """
    Create Loan Application
    ---
    tags:
      - Loan Application
    summary: Create a new Loan Application entry.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - applicant_type
              - applicant
              - applicant_email_address
              - applicant_phone_number
              - company
              - application_date
              - loan_product
              - repayment_method
    responses:
      201:
        description: Loan Application created successfully.
    """
    try:
        data = parse_api_payload()
        loan_application_data = service.create_loan_application(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Application created successfully.",
            data=loan_application_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        return handle_api_error(e, "Create Loan Application API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_application(id=None):
    """
    Update Loan Application
    ---
    tags:
      - Loan Application
    summary: Update specific attributes of a Loan Application.
    parameters:
      - in: query
        name: id
        required: true
    responses:
      200:
        description: Loan Application updated successfully.
    """
    try:
        data = parse_api_payload()
        loan_application_id = id or frappe.request.args.get("id")

        if not loan_application_id:
            raise frappe.ValidationError("Loan Application ID is required as a query parameter (?id=...).")

        loan_application_data = service.update_loan_application(loan_application_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Application updated successfully.",
            data=loan_application_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Loan Application API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_application_by_id(id=None):
    """
    Get Loan Application By ID
    ---
    tags:
      - Loan Application
    summary: Fetch full details of a Loan Application by ID.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        loan_application_id = id or frappe.request.args.get("id")

        if not loan_application_id:
            raise frappe.ValidationError("Loan Application ID is required.")

        data = service.get_loan_application_by_id(loan_application_id)

        return send_response(
            status="success",
            message="Loan Application retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Application By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_applications(page=1, page_size=20):
    """
    List Loan Applications
    ---
    tags:
      - Loan Application
    summary: Paginated list of Loan Applications with advanced filtering.
    parameters:
      - in: query
        name: page
      - in: query
        name: page_size
      - in: query
        name: search
      - in: query
        name: status
      - in: query
        name: applicant
      - in: query
        name: company
      - in: query
        name: loan_product
      - in: query
        name: minAmount
      - in: query
        name: maxAmount
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        loan_applications, total, total_pages = service.get_loan_applications(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Applications retrieved successfully.",
            "data": loan_applications,
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
        return handle_api_error(e, "Get All Loan Applications Error")

@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_loan_application(id=None):
    """
    Delete Loan Application
    ---
    tags:
      - Loan Application
    summary: Delete a Draft Loan Application.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        loan_application_id = id or frappe.local.form_dict.get("id")
        if not loan_application_id:
            raise frappe.ValidationError("Loan Application ID is required.")

        service.delete_loan_application(loan_application_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Application deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Loan Application Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_loan_application_status(id=None, action=None):
    """
    Update Loan Application Status (Approve/Reject)
    ---
    tags:
      - Loan Application
    summary: Updates the status of a Loan Application.
    parameters:
      - in: query
        name: id
        required: true
      - in: query
        name: action
        required: true
        schema:
          type: string
          enum: [approved, rejected]
    responses:
      200:
        description: Loan Application status updated successfully.
    """
    try:
        loan_application_id = id or frappe.request.args.get("id")
        action_value = action or frappe.request.args.get("action")

        if not loan_application_id:
            raise frappe.ValidationError("Loan Application ID is required.")

        if not action_value:
            raise frappe.ValidationError("Action is required (approved, rejected).")

        action_clean = str(action_value).strip().lower()

        if not frappe.db.exists("Loan Application", loan_application_id):
            raise frappe.DoesNotExistError(f"Loan Application '{loan_application_id}' not found")

        result = service.update_loan_application_status(loan_application_id, action_clean)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Loan Application {result['status']} successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Loan Application Status API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_countries(txt=None):
    """
    Get Countries
    ---
    tags:
      - Loan Application
    summary: Search/list countries for dropdown (link field autocomplete).
    parameters:
      - in: query
        name: txt
        schema:
          type: string
        required: false
    responses:
      200:
        description: Countries retrieved successfully.
    """
    try:
        search_term = txt or frappe.request.args.get("txt") or ""

        countries = frappe.get_all(
            "Country",
            filters={"name": ["like", f"%{search_term}%"]} if search_term else {},
            fields=["name as value", "name as label"],
            order_by="name asc",
            limit_page_length=0,
        )

        return send_response(
            status="success",
            message="Countries retrieved successfully.",
            data=countries,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Countries Error")