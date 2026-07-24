import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_loan():
    """
    Create Loan
    ---
    tags:
      - Loan
    summary: Create a new Loan entry.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - applicant_type
              - applicant
              - loan_product
              - loan_amount
            properties:
              applicant_type:
                type: string
              applicant:
                type: string
              loan_product:
                type: string
              loan_amount:
                type: number
    responses:
      201:
        description: Loan created successfully.
    """
    try:
        data = parse_api_payload()
        loan_data = service.create_loan(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan created successfully.",
            data=loan_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        return handle_api_error(e, "Create Loan API Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_loan(id=None):
    """
    Update Loan
    ---
    tags:
      - Loan
    summary: Update specific attributes of a Loan.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan updated successfully.
    """
    try:
        data = parse_api_payload()
        loan_id = id or frappe.request.args.get("id")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required as a query parameter (?id=...).")

        loan_data = service.update_loan(loan_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan updated successfully.",
            data=loan_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Loan API Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_by_id(id=None):
    """
    Get Loan By ID
    ---
    tags:
      - Loan
    summary: Fetch full details of a Loan by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        loan_id = id or frappe.request.args.get("id")
        
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")

        data = service.get_loan_by_id(loan_id)
        
        return send_response(
            status="success",
            message="Loan retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan By ID Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loans(page=1, page_size=20):
    """
    List Loans
    ---
    tags:
      - Loan
    summary: Paginated list of Loans with advanced filtering.
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

        loans, total_loans, total_pages = service.get_loans(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loans retrieved successfully.",
            "data": loans,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_loans,
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
        return handle_api_error(e, "Get All Loans Error")


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_loan(id=None):
    """
    Delete Loan
    ---
    tags:
      - Loan
    summary: Delete a Draft Loan.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        loan_id = id or frappe.local.form_dict.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")

        service.delete_loan(loan_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Loan Error")