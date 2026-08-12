import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from . import service

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_overview(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_loan_overview(loan_id)
        return send_response(status="success", message="Overview retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Loan Overview Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_schedule_summary(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_repayment_schedule_summary(loan_id)
        return send_response(status="success", message="Schedule retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment Schedule Timeline Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_history(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_repayment_history(loan_id)
        return send_response(status="success", message="History retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment History Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_accounting_ledger(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_loan_accounting_ledger(loan_id)
        return send_response(status="success", message="Ledger retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Accounting Ledger Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_collateral_view(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_collateral_view(loan_id)
        return send_response(status="success", message="Collateral retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Collateral View Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_documents(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_loan_documents(loan_id)
        return send_response(status="success", message="Documents retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Loan Documents Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_activity_audit(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_loan_activity_audit(loan_id)
        return send_response(status="success", message="Audit trail retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Audit Trail Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_disbursement_history(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_disbursement_history(loan_id)
        return send_response(status="success", message="Disbursements retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Disbursement History Error")