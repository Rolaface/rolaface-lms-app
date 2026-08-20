import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error, send_response_list
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_custom_loan_application():
    """
    Create Custom Loan Application
    ---
    tags:
      - Custom Loan Application
    summary: Create a new Custom Loan Application (Personal Loan or Business Loan).
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - application_type
    responses:
      201:
        description: Custom Loan Application created successfully.
    """
    try:
        data = parse_api_payload()
        loan_application_data = service.create_custom_loan_application(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Custom Loan Application created successfully.",
            data=loan_application_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        return handle_api_error(e, "Create Custom Loan Application API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_custom_loan_application_by_id(id=None):
    """
    Get Custom Loan Application By ID
    ---
    tags:
      - Custom Loan Application
    summary: Fetch full details of a Custom Loan Application by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        loan_application_id = id or frappe.request.args.get("id")

        if not loan_application_id:
            raise frappe.ValidationError("Custom Loan Application ID is required.")

        data = service.get_custom_loan_application_by_id(loan_application_id)

        return send_response(
            status="success",
            message="Custom Loan Application retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Custom Loan Application By ID Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_custom_loan_applications(page=1, page_size=20):
    """
    List Custom Loan Applications
    ---
    tags:
      - Custom Loan Application
    summary: Paginated list of Custom Loan Applications with filtering.
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
        name: application_type
      - in: query
        name: customer
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        loan_applications, total, total_pages = service.get_custom_loan_applications(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Custom Loan Applications retrieved successfully.",
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
        return handle_api_error(e, "Get All Custom Loan Applications Error")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def convert_custom_loan_application_to_loan(id=None):
    try:
        data = parse_api_payload()
        loan_application_id = id or frappe.request.args.get("id")

        if not loan_application_id:
            raise frappe.ValidationError("Custom Loan Application ID is required.")

        loan_product = data.get("loan_product")
        if not loan_product:
            raise frappe.ValidationError("'loan_product' is required to convert this application into a Loan.")

        # company = data.get("company")
        # if not company:
        #     raise frappe.ValidationError("'company' is required to convert this application into a Loan.")

        loan_data = service.convert_custom_loan_application_to_loan(loan_application_id, loan_product)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Custom Loan Application converted to Loan successfully.",
            data=loan_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        return handle_api_error(e, "Convert Custom Loan Application To Loan API Error")

@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_custom_loan_application(id=None):
    try:
        data = parse_api_payload()
        loan_application_id = id or frappe.request.args.get("id")

        if not loan_application_id:
            raise frappe.ValidationError("Custom Loan Application ID is required as a query parameter (?id=...).")

        loan_application_data = service.update_custom_loan_application(loan_application_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Custom Loan Application updated successfully.",
            data=loan_application_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Custom Loan Application API Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_custom_loan_application(id=None):
    try:
        loan_application_id = id or frappe.local.form_dict.get("id")
        if not loan_application_id:
            raise frappe.ValidationError("Custom Loan Application ID is required.")

        service.delete_custom_loan_application(loan_application_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Custom Loan Application deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Custom Loan Application Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_custom_loan_application_by_nrc(national_registration_card=None):
    """
    Get Custom Loan Application By NRC
    ---
    tags:
      - Custom Loan Application
    summary: Fetch full details of Custom Loan Application(s) by National Registration Card.
    parameters:
      - in: query
        name: national_registration_card
        schema:
          type: string
        required: true
    """
    try:
        nrc = national_registration_card or frappe.request.args.get("national_registration_card")

        if not nrc:
            raise frappe.ValidationError("National Registration Card is required.")

        data = service.get_custom_loan_applications_by_nrc(nrc)

        return send_response(
            status="success",
            message="Custom Loan Application(s) retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Custom Loan Application By NRC Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_custom_loan_application_by_email(email=None):
    """
    Get Custom Loan Application By Email
    ---
    tags:
      - Custom Loan Application
    summary: Fetch full details of Custom Loan Application(s) by email.
    parameters:
      - in: query
        name: email
        schema:
          type: string
        required: true
    """
    try:
        email_id = email or frappe.request.args.get("email")

        if not email_id:
            raise frappe.ValidationError("Email is required.")

        data = service.get_custom_loan_applications_by_email(email_id)

        return send_response(
            status="success",
            message="Custom Loan Application(s) retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Custom Loan Application By Email Error")