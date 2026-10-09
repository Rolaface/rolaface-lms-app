import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_investment_product():
    """
    Create Investment Product
    ---
    tags:
      - Investment Product
    summary: Create a new Investment Product.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - product_code
              - product_name
              - product_description
              - default_tenure
              - default_interest_rate
              - payout_frequency
              - min_interest_rate
              - maximum_interest_rate
              - minimum_investment
              - maximum_investment
              - minimum_tenure
              - maximum_tenure
            properties:
              product_code:
                type: string
                description: Unique, saved in UPPERCASE; cannot be changed after create.
              product_name:
                type: string
              product_description:
                type: string
              default_tenure:
                type: integer
                description: Months; between minimum_tenure and maximum_tenure.
              default_interest_rate:
                type: number
                description: Percent p.a.; between min_interest_rate and maximum_interest_rate.
              default_penalty_rate:
                type: number
                description: Optional, percent p.a.
              payout_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              disabled:
                type: integer
              min_interest_rate:
                type: number
              maximum_interest_rate:
                type: number
              minimum_investment:
                type: number
              maximum_investment:
                type: number
              minimum_tenure:
                type: integer
              maximum_tenure:
                type: integer
    responses:
      201:
        description: Investment Product created successfully.
    """
    try:
        data = parse_api_payload()
        result = service.create_investment_product(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investment Product created successfully.",
            data=result,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Investment Product API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investment_product(id=None):
    """
    Update Investment Product
    ---
    tags:
      - Investment Product
    summary: Update specific attributes of an Investment Product.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Investment Product updated successfully.
    """
    try:
        data = parse_api_payload()
        product_id = id or frappe.request.args.get("id")

        if not product_id:
            raise frappe.ValidationError("Investment Product ID is required as a query parameter (?id=...).")

        result = service.update_investment_product(product_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investment Product updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investment Product API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investment_product_by_id(id=None):
    """
    Get Investment Product By ID
    ---
    tags:
      - Investment Product
    summary: Fetch full details of an Investment Product by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        product_id = id or frappe.request.args.get("id")

        if not product_id:
            raise frappe.ValidationError("Investment Product ID is required.")

        data = service.get_investment_product_by_id(product_id)

        return send_response(
            status="success",
            message="Investment Product retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investment Product By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investment_product(page=1, page_size=20):
    """
    List Investment Products
    ---
    tags:
      - Investment Product
    summary: Paginated list of Investment Products with filtering.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID or product name.
      - in: query
        name: disabled
        schema:
          type: integer
          enum: [0, 1]
      - in: query
        name: payout_frequency
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

        records, total_records, total_pages = service.get_investment_products(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Investment Products retrieved successfully.",
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
        return handle_api_error(e, "Get All Investment Products Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_investment_product(id=None):
    """
    Delete Investment Product
    ---
    tags:
      - Investment Product
    summary: Delete an Investment Product.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        product_id = id or frappe.local.form_dict.get("id")
        if not product_id:
            raise frappe.ValidationError("Investment Product ID is required.")

        service.delete_investment_product(product_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investment Product deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Investment Product Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def enable_investment_product(id=None):
    """
    Enable Investment Product
    ---
    tags:
      - Investment Product
    summary: Sets the disabled flag to 0.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Investment Product enabled successfully.
    """
    try:
        product_id = id or frappe.request.args.get("id")
        if not product_id:
            raise frappe.ValidationError("Investment Product ID is required.")

        result = service.toggle_investment_product_status(product_id, disable_flag=0)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investment Product has been successfully enabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Enable Investment Product API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def disable_investment_product(id=None):
    """
    Disable Investment Product
    ---
    tags:
      - Investment Product
    summary: Sets the disabled flag to 1.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Investment Product disabled successfully.
    """
    try:
        product_id = id or frappe.request.args.get("id")
        if not product_id:
            raise frappe.ValidationError("Investment Product ID is required.")

        result = service.toggle_investment_product_status(product_id, disable_flag=1)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investment Product has been successfully disabled.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Disable Investment Product API Error")