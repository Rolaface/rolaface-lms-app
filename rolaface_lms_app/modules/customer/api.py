import frappe
from rolaface_lms_app.utils.api_response import (
    send_response,
    send_response_list,
    handle_api_error,
)
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_customer():
    """
    Create Customer
    ---
    tags:
      - Customer
    summary: Create a new Customer entry with Contacts and Addresses.
    """
    try:
        data = parse_api_payload()
        customer_data = service.create_customer(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Customer created successfully.",
            data=customer_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            db.rollback()
        return handle_api_error(e, "Create Customer API Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_customer(id=None):
    try:
        data = parse_api_payload()
        customer_id = id or frappe.request.args.get("id")

        if not customer_id:
            raise frappe.ValidationError("Customer ID is required as a query parameter (?id=...).")

        customer_data = service.update_customer(customer_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Customer updated successfully.",
            data=customer_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Customer API Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customer_by_id(id=None):
    try:
        customer_id = id or frappe.request.args.get("id")

        if not customer_id:
            raise frappe.ValidationError("Customer ID is required.")

        data = service.get_customer_by_id(customer_id)

        return send_response(
            status="success",
            message="Customer retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Customer By ID Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_customers(page=1, page_size=20):
    try:
        args = frappe.local.form_dict
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError):
            raise frappe.ValidationError("page and page_size must be integers.")

        if page < 1:
            raise frappe.ValidationError("page must be greater than or equal to 1.")
        if page_size < 1 or page_size > 100:
            raise frappe.ValidationError("page_size must be between 1 and 100.")

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        customers, total_customers, total_pages = service.get_customers(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Customers retrieved successfully.",
            "data": customers,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_customers,
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
        return handle_api_error(e, "Get All Customers Error")


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_customer(id=None):
    try:
        customer_id = id or frappe.local.form_dict.get("id")
        if not customer_id:
            raise frappe.ValidationError("Customer ID is required.")

        service.delete_customer(customer_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Customer deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Customer Error")


@frappe.whitelist(allow_guest=False, methods=["PUT", "PATCH"])
def update_customer_status(id=None, action=None):
    try:
        action_value = action or frappe.request.args.get("action")
        customer_id = id or frappe.request.args.get("id")

        if not customer_id:
            raise frappe.ValidationError("Customer ID is required.")
        if not action_value:
            raise frappe.ValidationError("Action is required (active, inactive).")

        action_clean = str(action_value).strip().lower()
        result = service.update_customer_status(customer_id, action_clean)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Customer status updated to {action_clean} successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        return handle_api_error(e, "Update Customer Status API Error")
