import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_allowed_workflow_actions(doctype, docname):
    """
    Returns the current state and available workflow actions for the UI.
    """
    try:
        if not doctype or not docname:
            raise frappe.ValidationError("doctype and docname are required query parameters.")

        workflow_data = service.get_allowed_workflow_actions(doctype, docname)

        return send_response(
            status="success",
            message="Workflow actions retrieved successfully.",
            data=workflow_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Workflow Actions Error")


@frappe.whitelist(allow_guest=False, methods=["POST"])
def process_dynamic_workflow_action():
    """
    Generic endpoint to process any workflow action for any doctype.
    """
    try:
        data = parse_api_payload()
        doctype = data.get("doctype", "Custom Loan Application")
        docname = data.get("docname")
        action = data.get("action")
        comment = data.get("comment")
        assign_to_user = data.get("assign_to_user")

        if not docname or not action:
            raise frappe.ValidationError("docname and action are strictly required.")

        result_data = service.apply_dynamic_workflow_action(
            doctype, docname, action, comment, assign_to_user
        )
        
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Action '{action}' applied successfully.",
            data=result_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Process Workflow Action Error")


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_workflow(doctype):
    try:
        if not doctype:
            raise frappe.ValidationError("doctype is required.")
        workflow_data = service.get_dynamic_workflow(doctype)
        return send_response(
            status="success",
            message="Workflow retrieved successfully.",
            data=workflow_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Workflow Error")

@frappe.whitelist(allow_guest=False, methods=["POST"])
def save_workflow():
    try:
        data = parse_api_payload()
        doctype = data.get("doctype")
        workflow_name = data.get("workflow_name")
        states = data.get("states", [])
        transitions = data.get("transitions", [])
        is_active = data.get("is_active", 1)

        if not doctype or not workflow_name:
            raise frappe.ValidationError("doctype and workflow_name are required.")

        result_data = service.save_dynamic_workflow(doctype, workflow_name, states, transitions, is_active)
        
        frappe.db.commit()

        return send_response(
            status="success",
            message="Workflow saved successfully.",
            data=result_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Save Workflow Error")