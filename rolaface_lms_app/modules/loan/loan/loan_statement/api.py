import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from . import service

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_statement_dashboard():
    try:
        loan_id = frappe.request.args.get("loan_id")
        from_date = frappe.request.args.get("from_date")
        to_date = frappe.request.args.get("to_date")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is a mandatory parameter.")

        data = service.loan_statement_dashboard(loan_id, from_date, to_date)
        
        return send_response(
            status="success", 
            message="Loan statement retrieved successfully", 
            data=data, 
            status_code=200
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Statement Error")



@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_statement(page=1, page_size=20):
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)
        
        loan_id = args.get("loan_id")
        from_date = args.get("from_date")
        to_date = args.get("to_date")
        search = args.get("search")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for the statement table.")

        statement_lines, total_records, total_pages = service.get_loan_statement(
            loan_id=loan_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
            search_term=search
        )

        response_data = {
            "success": True,
            "message": "Statement lines retrieved successfully.",
            "data": statement_lines,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response(
            status="success",
            message="Success",
            data=response_data,
            status_code=200
        )
    except Exception as e:
        return handle_api_error(e, "Get Paginated Statement Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def export_loan_statement_pdf():
    try:
        loan_id = frappe.request.args.get("loan_id")
        from_date = frappe.request.args.get("from_date")
        to_date = frappe.request.args.get("to_date")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for export.")

        pdf_bytes = service.generate_statement_pdf(loan_id, from_date, to_date)
        
        frappe.local.response.filename = f"Loan_Statement_{loan_id}.pdf"
        frappe.local.response.filecontent = pdf_bytes
        frappe.local.response.type = "pdf"
        
    except Exception as e:
        return handle_api_error(e, "Export Statement PDF Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def export_loan_statement_excel():
    try:
        loan_id = frappe.request.args.get("loan_id")
        from_date = frappe.request.args.get("from_date")
        to_date = frappe.request.args.get("to_date")

        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for export.")

        xlsx_data = service.generate_statement_excel(loan_id, from_date, to_date)
        
        frappe.local.response.filename = f"Loan_Statement_{loan_id}.xlsx"
        
        frappe.local.response.filecontent = xlsx_data.getvalue() if hasattr(xlsx_data, "getvalue") else xlsx_data
        
        frappe.local.response.type = "binary"
        
    except Exception as e:
        return handle_api_error(e, "Export Statement Excel Error")