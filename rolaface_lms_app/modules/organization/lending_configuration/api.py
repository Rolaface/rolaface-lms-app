import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

def _resolve_company(provided_company=None) -> str:
    company = provided_company or frappe.request.args.get("company") or frappe.local.form_dict.get("company")
    if not company:
        company = frappe.defaults.get_user_default("Company")
    if not company:
        raise frappe.ValidationError("Company parameter missing.")
    return company

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_lending_config():
    try:
        data = parse_api_payload()
        config_data = service.create_lending_config(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Configuration created.",
            data=config_data,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        if db := getattr(frappe.local, "db", None):
            try:
                db.rollback(chain=True)
            except TypeError:
                db.rollback()
        return handle_api_error(e, "Create Configuration Error")

@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_lending_config(company=None):
    try:
        data = parse_api_payload()
        target_company = _resolve_company(company)
        config_data = service.update_lending_config(target_company, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Configuration updated.",
            data=config_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Update Configuration Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_lending_config(company=None):
    try:
        target_company = _resolve_company(company)
        data = service.get_lending_config(target_company)

        return send_response(
            status="success",
            message="Configuration retrieved.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Configuration Error")

@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_lending_config(company=None):
    try:
        target_company = _resolve_company(company)
        service.delete_lending_config(target_company)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Configuration deleted.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Delete Configuration Error")