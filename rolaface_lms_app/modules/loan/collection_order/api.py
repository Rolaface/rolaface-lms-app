import frappe
from . import service
from rolaface_lms_app.utils.api_response import send_response, send_response_list

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_all(search=None, order_by="creation desc", page=1, page_size=10):
    try:
        collection_order = service.get_collection_order(search, order_by, page, page_size)
        return send_response_list(
                    status="success",
                    message="Success",
                    status_code=200,
                    data=collection_order,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get(name):
    try:
        if not name:
            raise frappe.throw("Please supply Collection Order")
        collection_order = service.get_collection_order_by_name(name)
        return send_response(
                    status="success",
                    message="Success",
                    status_code=200,
                    data=collection_order,
                    http_status=200,
                )
    except frappe.DoesNotExistError:
        return send_response(
                            status="error",
                            message=f"Collection Sequence Order {name} not found",
                            status_code=500,
                            http_status=500,
                        )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create():
    try:
        payload = frappe.local.form_dict
        collection_order = service.create_collection_order(payload)
        return send_response(
                    status="success",
                    message=f"Collection Order {collection_order} successfully created.",
                    status_code=201,
                    http_status=201,
                )

    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update():
    try:
        payload = frappe.local.form_dict
        collection_order = service.update_collection_order(payload)
        return send_response(
                    status="success",
                    message=f"Collection Order successfully Updated.",
                    status_code=200,
                    http_status=200,
                )
    except Exception as e:
        return send_response(
                    status="error",
                    message=f"{str(e)}",
                    status_code=500,
                    http_status=500,
                )
