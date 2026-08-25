import frappe
from rolaface_lms_app.utils.api_response import send_response, handle_api_error
from . import service
from frappe.utils import getdate

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_statement_dashboard(loan_id=None, from_date=None, to_date=None, view_type="detailed", **kwargs):
    try:
        if not loan_id:
            raise frappe.ValidationError("Loan ID is a mandatory parameter.")

        data = service.loan_statement_dashboard(loan_id, from_date, to_date, view_type)
        
        return send_response(
            status="success", 
            message="Loan statement retrieved successfully", 
            data=data, 
            status_code=200
        )
    except Exception as e:
        return handle_api_error(e, "Get Loan Statement Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_loan_statement(loan_id=None, from_date=None, to_date=None, page=1, page_size=20, search=None, view_type="detailed", transaction_type=None, sort_by="date", sort_order="asc", **kwargs):
    try:
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for the statement table.")

        page = int(page) if str(page).isdigit() else 1
        page_size = int(page_size) if str(page_size).isdigit() else 20

        statement_lines, total_records, total_pages = service.get_loan_statement(
            loan_id=loan_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
            search_term=search,
            view_type=view_type,
            transaction_type=transaction_type,
            sort_by=sort_by,
            sort_order=sort_order
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
def export_loan_statement_pdf(loan_id=None, from_date=None, to_date=None, view_type="detailed", **kwargs):
    try:
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for export.")

        pdf_bytes = service.generate_statement_pdf(loan_id, from_date, to_date, view_type)
        
        frappe.local.response.filename = f"Loan_Statement_{loan_id}.pdf"
        frappe.local.response.filecontent = pdf_bytes
        frappe.local.response.type = "pdf"
        
    except Exception as e:
        return handle_api_error(e, "Export Statement PDF Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def export_loan_statement_excel(loan_id=None, from_date=None, to_date=None, view_type="detailed", **kwargs):
    try:
        if not loan_id:
            raise frappe.ValidationError("Loan ID is required for export.")

        xlsx_data = service.generate_statement_excel(loan_id, from_date, to_date, view_type)
        
        frappe.local.response.filename = f"Loan_Statement_{loan_id}.xlsx"
        frappe.local.response.filecontent = xlsx_data.getvalue() if hasattr(xlsx_data, "getvalue") else xlsx_data
        frappe.local.response.type = "binary"
        
    except Exception as e:
        return handle_api_error(e, "Export Statement Excel Error")

@frappe.whitelist(allow_guest=False, methods=["POST"])
def send_loan_statment():
    try:
        args = frappe.local.form_dict
        loan_id = args.get("loan_id")
        from_date = args.get("from_date")
        to_date = args.get("to_date")
        customer_id = args.get("customer_id")
        pdf = service.generate_statement_pdf(loan_id, from_date, to_date)
        customer_email, customer_name = frappe.db.get_value(
                                                                "Customer", customer_id, ["email_id", "customer_name"]
                                                            )
        
        formatted_from_date = getdate(from_date).strftime("%d %B %Y") if from_date else None
        formatted_to_date = getdate(to_date).strftime("%d %B %Y") if to_date else None

        frappe.sendmail(
            recipients=[customer_email],
            subject=f"Loan Statement — {loan_id}",
            message=f"Dear {customer_name},<br><br>"
                    f"Please find attached your loan statement for {loan_id}"
                    f"{f' covering {formatted_from_date} to {formatted_to_date}' if from_date and to_date else ''}.<br><br>"
                    f"Kindly review the attached statement and contact us should you require any clarification.<br><br>"
                    f"Regards,<br>{frappe.defaults.get_user_default('Company') or ''}",

            attachments=[{
                "fname": f"Loan_Statement_{loan_id}.pdf",
                "fcontent": pdf,
            }],
            now=True
        )
        return send_response(
                    status="success",
                    message="Success",
                    data=None,
                    status_code=200
                )
    except Exception as e:
        return send_response(
                status="error",
                message="Internal Server Error",
                status_code=500,
                http_status=500,
            )