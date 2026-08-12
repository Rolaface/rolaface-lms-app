import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from . import service

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_statement():
    try:
        loan_id = frappe.request.args.get("loan_id")
        from_date = frappe.request.args.get("from_date")
        to_date = frappe.request.args.get("to_date")

        if not loan_id or not from_date or not to_date:
            raise frappe.ValidationError("Loan ID, From Date, and To Date are mandatory parameters.")

        data = service.generate_loan_statement(loan_id, from_date, to_date)
        
        return send_response(
            status="success", 
            message="Loan statement retrieved successfully", 
            data=data, 
            status_code=200
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Statement Error")