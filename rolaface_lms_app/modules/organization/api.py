from .service import (get_company_details, update_company_details, upload_file, remove_attach,
                                                          get_company_defaults_data, update_company_defaults_data, get_company_lending_setup, update_company_lending_setup)
from rolaface_lms_app.utils.api_response import send_old_response, send_response
import frappe
# from custom_api.permission import require_permission

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get():
    try:
        data = get_company_details()

        return send_old_response(
            status="success",
            message="Company retrieved successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except frappe.DoesNotExistError:
        return send_old_response(
            status="fail",
            message="Company not found",
            status_code=404,
            http_status=404
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Company API Error")
        return send_old_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=True, methods=["POST", "PUT"])
# @require_permission("Company", "write")
def update():
    try:
        data = frappe.local.form_dict

        updated_company = update_company_details(data)

        return send_old_response(
            status="success",
            message="Company updated successfully",
            data=updated_company,
            status_code=200,
            http_status=200
        )

    except frappe.DoesNotExistError:
        return send_old_response(
            status="fail",
            message="Company not found",
            status_code=404,
            http_status=404
        )

    except frappe.ValidationError as ve:
        return send_old_response(
            status="fail",
            message=str(ve),
            status_code=400,
            http_status=400
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Update Company API Error")
        return send_old_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
    
@frappe.whitelist(allow_guest=True, methods=["PATCH"])
# @require_permission("Company", "write")
def upload_company_documents():
    try:
        company_name = frappe.defaults.get_user_default("Company")

        if not company_name:
            frappe.throw("No default company set")

        company = frappe.get_doc("Company", company_name)

        # Files from request
        company_logo_file = frappe.local.request.files.get("documents[companyLogoUrl]")
        signature_file = frappe.local.request.files.get("documents[authorizedSignatureUrl]")

        # Save logo
        if company_logo_file:
            remove_attach("Company", company.name, "company_logo")
            respone = upload_file(company_logo_file, "Company", company.name, "company_logo")
            company.company_logo = respone.file_url
            
        # Save signature
        signature_url = None
        if signature_file:
            remove_attach("Company", company.name, "custom_company_signature")
            signature_url = upload_file(signature_file, "Company", company.name, "custom_company_signature")
            company.custom_company_signature = signature_url.file_url

        company.save(ignore_permissions=True)

        return send_old_response(
            status="success",
            message="Company documents uploaded successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Upload Company Documents API Error")

        return send_old_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
    
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_company_defaults():
    try:
        data = get_company_defaults_data()
 
        return send_response(
            status="success",
            message="Company defaults retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Company Defaults API Error")
        return send_response(
            status="error",
            message=str(e),
            status_code=500,
            http_status=500,
        )
    
@frappe.whitelist(allow_guest=True, methods=["PUT"])
# @require_permission("Company", "write")
def update_company_defaults():
    try:
        data = update_company_defaults_data(
            frappe.local.form_dict
        )

        return send_response(
            status="success",
            message="Company defaults updated successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )

    except frappe.ValidationError as e:
        return send_response(
            status="error",
            message=str(e),
            status_code=400,
            http_status=400,
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Company Defaults API Error"
        )

        return send_response(
            status="error",
            message=str(e),
            status_code=500,
            http_status=500,
        )
    
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_company_lending_defaults():
    try:
        data = get_company_lending_setup()
 
        return send_response(
            status="success",
            message="Company defaults retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Company Defaults API Error")
        return send_response(
            status="error",
            message=str(e),
            status_code=500,
            http_status=500,
        )
    
@frappe.whitelist(allow_guest=True, methods=["PUT"])
# @require_permission("Company", "write")
def update_company_lending_defaults():
    try:
        data = update_company_lending_setup(
            frappe.local.form_dict
        )

        return send_response(
            status="success",
            message="Company defaults updated successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )

    except frappe.ValidationError as e:
        return send_response(
            status="error",
            message=str(e),
            status_code=400,
            http_status=400,
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Company Defaults API Error"
        )

        return send_response(
            status="error",
            message=str(e),
            status_code=500,
            http_status=500,
        )