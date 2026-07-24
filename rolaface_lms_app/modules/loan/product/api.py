import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload

from . import service


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_loan_product():
    """
    Create Loan Product
    ---
    tags:
      - Loan Product
    summary: Create a new loan product configuration.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - product_code
              - product_name
            properties:
              product_code:
                type: string
              product_name:
                type: string
              rate_of_interest:
                type: number
              maximum_loan_amount:
                type: number
              company:
                type: string
    responses:
      201:
        description: Loan Product created successfully.
      400:
        description: Validation error (e.g., negative interest rate, missing fields).
      409:
        description: Duplicate Entry (code or name exists).
    """
    try:
        data = parse_api_payload()
        product_data = service.create_loan_product(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Product created successfully.",
            data=product_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        return handle_api_error(e, "Create Loan Product API Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_loan_product(id=None):
    """
    Update Loan Product
    ---
    tags:
      - Loan Product
    summary: Update specific attributes of a Loan Product.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
        description: The ID of the Loan Product.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
    responses:
      200:
        description: Loan Product updated successfully.
      400:
        description: Validation Error.
      404:
        description: Loan Product not found.
    """
    try:
        data = parse_api_payload()
        product_id = id or frappe.request.args.get("id")

        if not product_id:
            raise frappe.ValidationError("Loan Product ID is required as a query parameter (?id=...).")

        product_data = service.update_loan_product(product_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Product updated successfully.",
            data=product_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Loan Product API Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_product_by_id(id=None):
    """
    Get Loan Product
    ---
    tags:
      - Loan Product
    summary: Fetch full details of a Loan Product by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Successful operation.
      404:
        description: Loan Product not found.
    """
    try:
        product_id = id or frappe.request.args.get("id")
        
        if not product_id:
            raise frappe.ValidationError("Loan Product ID is required.")

        data = service.get_loan_product_by_id(product_id)
        
        return send_response(
            status="success",
            message="Loan Product retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Product By ID Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_loan_products(page=1, page_size=20):
    """
    List Loan Products
    ---
    tags:
      - Loan Product
    summary: Paginated list of Loan Products with advanced filtering.
    parameters:
      - in: query
        name: page
        schema:
          type: integer
      - in: query
        name: page_size
        schema:
          type: integer
      - in: query
        name: search
        schema:
          type: string
      - in: query
        name: disabled
        schema:
          type: integer
          enum: [0, 1]
      - in: query
        name: company
        schema:
          type: string
      - in: query
        name: minRate
        schema:
          type: number
      - in: query
        name: maxRate
        schema:
          type: number
      - in: query
        name: minAmount
        schema:
          type: number
      - in: query
        name: maxAmount
        schema:
          type: number
      - in: query
        name: loan_category
        schema:
          type: string
      - in: query
        name: sort_by
        schema:
          type: string
      - in: query
        name: sort_order
        schema:
          type: string
          enum: [asc, desc]
    responses:
      200:
        description: A list of loan products.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        products, total_products, total_pages = service.get_loan_products(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Loan Products retrieved successfully.",
            "data": products,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_products,
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
        return handle_api_error(e, "Get All Loan Products Error")


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_loan_product(id=None):
    """
    Delete Loan Product
    ---
    tags:
      - Loan Product
    summary: Delete a Loan Product if no active loans are linked.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Product deleted successfully.
      400:
        description: Validation Error (e.g., linked to active loans).
      404:
        description: Loan Product not found.
    """
    try:
        product_id = id or frappe.local.form_dict.get("id")
        if not product_id:
            raise frappe.ValidationError("Loan Product ID is required.")

        service.delete_loan_product(product_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Product deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Loan Product Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def enable_loan_product(id=None):
    """
    Enable Loan Product
    ---
    tags:
      - Loan Product Status
    summary: Sets the disabled flag to 0.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Product enabled successfully.
    """
    try:
        product_id = id or frappe.request.args.get("id")
        if not product_id:
            raise frappe.ValidationError("Loan Product ID is required.")

        result = service.toggle_loan_product_status(product_id, disable_flag=0)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Product has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Enable Loan Product API Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def disable_loan_product(id=None):
    """
    Disable Loan Product
    ---
    tags:
      - Loan Product Status
    summary: Sets the disabled flag to 1.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Loan Product disabled successfully.
    """
    try:
        product_id = id or frappe.request.args.get("id")
        if not product_id:
            raise frappe.ValidationError("Loan Product ID is required.")

        result = service.toggle_loan_product_status(product_id, disable_flag=1)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Loan Product has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Disable Loan Product API Error")