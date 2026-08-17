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
def get_installment_detail(id=None, idx=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        installment_idx = idx or frappe.request.args.get("idx")
        
        if not loan_id or not installment_idx:
            raise frappe.ValidationError("Loan ID and Installment IDX are required.")
            
        data = service.get_installment_detail(loan_id, int(installment_idx))
        return send_response(status="success", message="Installment detail retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Installment Detail Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_schedule_timeline(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_repayment_schedule_timeline(loan_id)
        return send_response(status="success", message="Timeline retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment Schedule Timeline Error")
    
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_schedule_versions(id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_repayment_schedule_versions(loan_id)
        return send_response(status="success", message="Schedule versions retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment Schedule Versions Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_schedule(id=None, schedule_id=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        sch_id = schedule_id or frappe.request.args.get("schedule_id")
        
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        data = service.get_repayment_schedule(loan_id, sch_id)
        return send_response(status="success", message="Schedule retrieved", data=data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment Schedule Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_repayment_history(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_repayment_history(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "History retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Repayment History Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_accounting_ledger(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_loan_accounting_ledger(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "Ledger retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Accounting Ledger Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_collateral_view(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_collateral_view(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "Collateral retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Collateral View Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_documents(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_loan_documents(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "Documents retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Loan Documents Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_activity_audit(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_loan_activity_audit(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "Audit trail retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Audit Trail Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_disbursement_history(id=None, page=1, page_size=20, search=None):
    try:
        loan_id = id or frappe.request.args.get("id")
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required.")
            
        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        records, total_records, total_pages = service.get_disbursement_history(loan_id, page, page_size, search)
        
        response_data = {
            "success": True,
            "message": "Disbursements retrieved successfully.",
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

        return send_response(status="success", message="Success", data=response_data, status_code=200)
    except Exception as e:
        return handle_api_error(e, "Get Disbursement History Error")