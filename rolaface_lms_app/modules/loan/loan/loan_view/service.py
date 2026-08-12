import frappe
from frappe.query_builder import DocType, Order
from typing import Dict, Any, List

from rolaface_lms_app.modules.loan.loan.api import get_loan_by_id
from .utils import format_audit_timeline


def get_loan_overview(loan_id: str) -> Dict[str, Any]:
    """
    Fetches the base loan form details. Reuses your existing CRUD logic 
    but can be extended to calculate view-specific KPIs.
    """
    try:
        base_loan = get_loan_by_id(loan_id)
        
        loan_amount = frappe.utils.flt(base_loan.get("loan_amount", 0))
        principal_paid = frappe.utils.flt(base_loan.get("total_principal_paid", 0))
        base_loan["kpi_outstanding_principal"] = max(0, loan_amount - principal_paid)
        
        return base_loan
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Overview Error")
        raise frappe.ValidationError(f"Failed to fetch loan overview: {str(e)}")


def get_repayment_history(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches the repayment history using Query Builder for maximum performance.
    Maps strictly to the provided Loan Repayment schema.
    """
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        lr = DocType("Loan Repayment")
        
        query = (
            frappe.qb.from_(lr)
            .select(
                lr.name.as_("receipt_no"),
                lr.posting_date.as_("payment_date"),
                lr.mode_of_payment.as_("method"),
                lr.amount_paid,
                lr.principal_amount_paid.as_("principal"),
                lr.total_interest_paid.as_("interest"),
                lr.total_penalty_paid.as_("penalty")
            )
            .where(
                (lr.against_loan == loan_id) & 
                (lr.docstatus == 1)
            )
            .orderby(lr.posting_date, order=Order.desc)
        )
        
        return query.run(as_dict=True)
        
    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Repayment History Error")
        raise frappe.ValidationError(f"Failed to fetch repayment history: {str(e)}")


def get_disbursement_history(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches the disbursement tranches using Query Builder.
    Maps strictly to the provided Loan Disbursement schema.
    """
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        ld = DocType("Loan Disbursement")
        
        query = (
            frappe.qb.from_(ld)
            .select(
                ld.name,
                ld.loan_product,
                ld.disbursement_date,
                ld.disbursement_account,
                ld.sanctioned_loan_amount,
                ld.disbursed_amount,
                ld.current_disbursed_amount.as_("disbursed_till_now"),
                ld.status,
                ld.tranche_number,
                ld.reference_number,
                ld.monthly_repayment_amount,
                ld.repayment_method,
                ld.repayment_start_date,
                ld.repayment_schedule_type,
                ld.mode_of_payment,
                ld.bank_account,
                # ld.loan_disbursement_charges,
            )
            .where(
                (ld.against_loan == loan_id) & 
                (ld.docstatus < 2)
            )
            .orderby(ld.disbursement_date, order=Order.desc)
        )
        
        return query.run(as_dict=True)
        
    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Disbursement History Error")
        raise frappe.ValidationError(f"Failed to fetch disbursement history: {str(e)}")


def get_repayment_schedule_summary(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches the parent schedule metadata using Query Builder. 
    Maps strictly to the provided Loan Repayment Schedule header schema.
    """
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        lrs = DocType("Loan Repayment Schedule")
        
        query = (
            frappe.qb.from_(lrs)
            .select(
                lrs.name,
                lrs.repayment_start_date,
                lrs.maturity_date,
                lrs.monthly_repayment_amount,
                lrs.total_installments_paid,
                lrs.total_installments_raised,
                lrs.total_installments_overdue,
                lrs.current_principal_amount
            )
            .where(
                (lrs.loan == loan_id) & 
                (lrs.docstatus == 1)
            )
            .orderby(lrs.creation, order=Order.desc)
        )
        
        return query.run(as_dict=True)
        
    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Schedule Summary Error")
        raise frappe.ValidationError(f"Failed to fetch schedule summary: {str(e)}")


def get_loan_accounting_ledger(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches strictly filtered GL Entries associated with this specific loan.
    Requires pulling the voucher references first to link the GL to the loan.
    """
    try:
        # Fetch Voucher Names (Disbursements and Repayments)
        ld = DocType("Loan Disbursement")
        lr = DocType("Loan Repayment")
        
        disbursements = frappe.qb.from_(ld).select(ld.name).where((ld.against_loan == loan_id) & (ld.docstatus == 1)).run(pluck=True)
        repayments = frappe.qb.from_(lr).select(lr.name).where((lr.against_loan == loan_id) & (lr.docstatus == 1)).run(pluck=True)
        
        vouchers = disbursements + repayments
        
        if not vouchers:
            return []

        gl = DocType("GL Entry")
        query = (
            frappe.qb.from_(gl)
            .select(
                gl.posting_date,
                gl.voucher_type,
                gl.voucher_no.as_("description"),
                gl.debit,
                gl.credit,
                gl.account
            )
            .where(
                (gl.voucher_no.isin(vouchers)) & 
                (gl.is_cancelled == 0)
            )
            .orderby(gl.posting_date, order=Order.desc)
            .orderby(gl.creation, order=Order.desc)
        )
        
        return query.run(as_dict=True)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Accounting Ledger Error")
        raise frappe.ValidationError(f"Failed to fetch accounting ledger: {str(e)}")


def get_collateral_view(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches the security assignments and child items linked to the loan.
    Utilizes the proven extraction logic from existing CRUD operations.
    """
    try:
        assignments = frappe.get_all(
            "Loan Security Assignment",
            filters={"loan": loan_id, "docstatus": ["<", 2]},
            fields=[
                "name",
                "status",
                "applicant_type",
                "applicant",
                "total_security_value",
                "maximum_loan_value",
                "reference_no",
                "description",
            ],
        )
        
        result = []
        for assignment_info in assignments:
            assignment_doc = frappe.get_doc(
                "Loan Security Assignment", assignment_info.name
            )

            items = []
            for row in assignment_doc.get("securities") or []:
                items.append(
                    {
                        "loan_security": row.get("loan_security"),
                        "loan_security_name": row.get("loan_security_name"),
                        "loan_security_type": row.get("loan_security_type"),
                        "loan_security_code": row.get("loan_security_code"),
                        "qty": row.get("qty"),
                        "loan_security_price": row.get("loan_security_price"),
                        "haircut_percent": row.get("haircut"),
                        "haircut_amount": row.get("amount") - row.get("post_haircut_amount"),
                        "post_haircut_amount": row.get("post_haircut_amount"),
                        "amount": row.get("amount", 0),
                    }
                )

            assignment_info["items"] = items
            result.append(assignment_info)
            
        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Collateral Error")
        raise frappe.ValidationError(f"Failed to fetch collateral: {str(e)}")


def get_loan_documents(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches attachments directly from the core File doctype using Query Builder.
    """
    try:
        f = DocType("File")
        
        query = (
            frappe.qb.from_(f)
            .select(
                f.name,
                f.file_name,
                f.file_url,
                f.file_size,
                f.creation,
                f.is_private
            )
            .where(
                (f.attached_to_doctype == "Loan") & 
                (f.attached_to_name == loan_id)
            )
            .orderby(f.creation, order=Order.desc)
        )
        
        return query.run(as_dict=True)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Documents Error")
        raise frappe.ValidationError(f"Failed to fetch documents: {str(e)}")


def get_loan_activity_audit(loan_id: str) -> List[Dict[str, Any]]:
    """
    Aggregates Versions, Comments, and Communications into a unified timeline.
    Uses direct DB queries with strict limits for performance.
    """
    try:
        # Fetching raw dicts directly to avoid full doc hydration overhead
        versions = frappe.get_all("Version", filters={"ref_doctype": "Loan", "docname": loan_id}, fields=["name", "owner", "creation", "data"], limit=30)
        comments = frappe.get_all("Comment", filters={"reference_doctype": "Loan", "reference_name": loan_id}, fields=["name", "comment_type", "content", "owner", "creation"], limit=30)
        comms = frappe.get_all("Communication", filters={"reference_doctype": "Loan", "reference_name": loan_id}, fields=["name", "communication_type", "content", "sender as owner", "creation"], limit=30)
        
        return format_audit_timeline(versions, comments, comms)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Audit Trail Error")
        raise frappe.ValidationError(f"Failed to fetch audit trail: {str(e)}")