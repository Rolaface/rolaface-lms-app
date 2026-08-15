import frappe
from frappe.query_builder import DocType, Order
from typing import Dict, Any, List

from rolaface_lms_app.modules.loan.loan.api import get_loan_by_id
from .utils import format_audit_timeline, calculate_timeline_statuses


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
                lr.name,
                lr.posting_date,
                lr.mode_of_payment,
                lr.amount_paid,
                lr.principal_amount_paid,
                lr.total_interest_paid,
                lr.total_penalty_paid,
                lr.total_charges_paid,
                lr.pending_principal_amount
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

def get_repayment_schedule_versions(loan_id: str) -> List[Dict[str, Any]]:

    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        lrs = DocType("Loan Repayment Schedule")
        
        query = (
            frappe.qb.from_(lrs)
            .select(
                lrs.name.as_("id"),
                lrs.repayment_start_date.as_("active_from"),
                lrs.maturity_date.as_("active_till"),
                lrs.creation,
                lrs.status,
                lrs.creation.as_("valid_from"),
                lrs.modified.as_("valid_till"),
            )
            .where(
                (lrs.loan == loan_id) & 
                (lrs.docstatus == 1)
            )
            .orderby(lrs.creation, order=Order.desc)
        )
        
        versions = query.run(as_dict=True)
        
        for idx, version in enumerate(versions):
            version["is_active"] = (idx == 0)
            
        return versions
        
    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Schedule Versions Error")
        raise frappe.ValidationError(f"Failed to fetch schedule versions: {str(e)}")


def get_repayment_schedule_summary(loan_id: str, schedule_id: str = None) -> Dict[str, Any]:
    """
    Fetches the parent schedule metadata and its individual timeline installments.
    If schedule_id is provided, fetches that specific version.
    If not, defaults to the latest active version.
    """
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        lrs = DocType("Loan Repayment Schedule")
        
        parent_query = (
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
        )
        
        if schedule_id:
            parent_query = parent_query.where(lrs.name == schedule_id)
        else:
            parent_query = parent_query.orderby(lrs.creation, order=Order.desc).limit(1)
            
        parent_result = parent_query.run(as_dict=True)
        
        if not parent_result:
            return {}
            
        schedule_summary = parent_result[0]
        
        rs = DocType("Repayment Schedule")
        
        child_query = (
            frappe.qb.from_(rs)
            .select(
                rs.idx,
                rs.payment_date,
                rs.number_of_days,
                rs.principal_amount,
                rs.interest_amount,
                rs.total_payment,
                rs.balance_loan_amount,
                rs.charges,
                rs.demand_generated
            )
            .where(
                (rs.parent == schedule_summary["name"]) &
                (rs.parenttype == "Loan Repayment Schedule")
            )
            .orderby(rs.idx, order=Order.asc)
        )
        
        schedule_summary["repayment_schedule"] = child_query.run(as_dict=True)
        
        return schedule_summary
        
    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Schedule Summary Error")
        raise frappe.ValidationError(f"Failed to fetch schedule summary: {str(e)}")
    
def get_repayment_schedule_timeline(loan_id: str) -> Dict[str, Any]:

    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        lrs = DocType("Loan Repayment Schedule")
        parent_query = (
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
            .where((lrs.loan == loan_id) & (lrs.docstatus == 1))
            .orderby(lrs.creation, order=Order.desc)
            .limit(1)
        )
        
        parent_result = parent_query.run(as_dict=True)
        if not parent_result:
            return {}
            
        schedule_summary = parent_result[0]
        parent_name = schedule_summary["name"]

        rs = DocType("Repayment Schedule")
        raw_schedule = (
            frappe.qb.from_(rs)
            .select(
                rs.idx, 
                rs.payment_date, 
                rs.total_payment,
                rs.principal_amount.as_("principal"),
                rs.interest_amount.as_("interest")
            )
            .where((rs.parent == parent_name) & (rs.parenttype == "Loan Repayment Schedule"))
            .orderby(rs.idx, order=Order.asc)
            .run(as_dict=True)
        )

        lr = DocType("Loan Repayment")
        actual_repayments = (
            frappe.qb.from_(lr)
            .select(
                lr.posting_date.as_("payment_date"), 
                lr.principal_amount_paid.as_("principal"), 
                lr.total_interest_paid.as_("interest")
            )
            .where((lr.against_loan == loan_id) & (lr.docstatus == 1))
            .orderby(lr.posting_date, order=Order.asc)
            .run(as_dict=True)
        )

        enriched_schedule = calculate_timeline_statuses(raw_schedule, actual_repayments)

        lightweight_timeline = []
        for row in enriched_schedule:
            lightweight_timeline.append({
                "idx": row["idx"],
                "payment_date": row["payment_date"],
                "total_payment": row["total_payment"],
                "ui_status": row["ui_status"]
            })

        schedule_summary["timeline"] = lightweight_timeline

        return schedule_summary

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Schedule Timeline Error")
        raise frappe.ValidationError(f"Failed to fetch schedule timeline: {str(e)}")


def get_installment_detail(loan_id: str, installment_idx: int) -> Dict[str, Any]:

    try:
        lrs = DocType("Loan Repayment Schedule")
        parent_name = frappe.qb.from_(lrs).select(lrs.name).where((lrs.loan == loan_id) & (lrs.docstatus == 1)).orderby(lrs.creation, order=Order.desc).limit(1).run(pluck=True)
        
        if not parent_name:
            raise frappe.ValidationError("No active Repayment Schedule found for this loan.")

        rs = DocType("Repayment Schedule")
        detailed_row = (
            frappe.qb.from_(rs)
            .select(
                rs.idx,
                rs.payment_date,
                rs.principal_amount.as_("principal"),
                rs.interest_amount.as_("interest"),
                rs.total_payment,
                rs.balance_loan_amount,
                rs.charges
            )
            .where((rs.parent == parent_name[0]) & (rs.parenttype == "Loan Repayment Schedule") & (rs.idx == installment_idx))
            .run(as_dict=True)
        )
        
        if not detailed_row:
            raise frappe.DoesNotExistError(f"Installment {installment_idx} does not exist.")
            
        target_installment = detailed_row[0]


        raw_schedule = frappe.qb.from_(rs).select(rs.idx, rs.payment_date, rs.total_payment, rs.principal_amount.as_("principal"), rs.interest_amount.as_("interest")).where((rs.parent == parent_name[0])).orderby(rs.idx, order=Order.asc).run(as_dict=True)
        
        lr = DocType("Loan Repayment")
        actual_repayments = frappe.qb.from_(lr).select(lr.posting_date.as_("payment_date"), lr.principal_amount_paid.as_("principal"), lr.total_interest_paid.as_("interest")).where((lr.against_loan == loan_id) & (lr.docstatus == 1)).orderby(lr.posting_date, order=Order.asc).run(as_dict=True)
        
        enriched_schedule = calculate_timeline_statuses(raw_schedule, actual_repayments)
        
        calculated_status = next((item["ui_status"] for item in enriched_schedule if item["idx"] == installment_idx), "Upcoming")
        
        target_installment["ui_status"] = calculated_status
        target_installment["penalty"] = 0.0 # Standard Frappe Repayment Schedule doesn't hold projected penalty

        return target_installment

    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Installment Detail Error")
        raise frappe.ValidationError(f"Failed to fetch installment {installment_idx}: {str(e)}")
    
    
def get_loan_accounting_ledger(loan_id: str) -> List[Dict[str, Any]]:
    """
    Fetches strictly filtered GL Entries associated with this specific loan.
    Requires pulling the voucher references first to link the GL to the loan.
    """
    try:
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
    Aggregates comprehensive loan activities (Notes, Communications, Repayments, 
    Accruals, Restructures, and System Versions) into a unified timeline perfectly 
    formatted for the UI widget.
    """
    try:
        if not frappe.db.exists("Loan", loan_id):
            raise frappe.DoesNotExistError(f"Loan '{loan_id}' does not exist.")

        timeline = []

        # 1. User Notes (Comments)
        comment = DocType("Comment")
        comments = frappe.qb.from_(comment).select(
            comment.name.as_("id"), comment.creation.as_("timestamp"), 
            comment.owner.as_("actor"), comment.content
        ).where(
            (comment.reference_doctype == "Loan") & 
            (comment.reference_name == loan_id) & 
            (comment.comment_type == "Comment")
        ).run(as_dict=True)

        for c in comments:
            timeline.append({
                "id": c["id"], 
                "type": "note", 
                "timestamp": c["timestamp"], 
                "actor": c["actor"],
                "title": "Account Note", 
                "subtitle": frappe.utils.strip_html_tags(c["content"])[:150]
            })

        # 2. Communications (Calls, SMS, Emails)
        comm = DocType("Communication")
        comms = frappe.qb.from_(comm).select(
            comm.name.as_("id"), comm.creation.as_("timestamp"), comm.sender.as_("actor"),
            comm.communication_type, comm.communication_medium, comm.subject, comm.content
        ).where(
            (comm.reference_doctype == "Loan") & (comm.reference_name == loan_id)
        ).run(as_dict=True)

        for c in comms:
            # Map Frappe medium to UI type
            c_type = "email"
            if c["communication_medium"] == "Phone": c_type = "call"
            elif c["communication_medium"] == "SMS": c_type = "msg"

            timeline.append({
                "id": c["id"], 
                "type": c_type, 
                "timestamp": c["timestamp"], 
                "actor": c["actor"],
                "title": c["subject"] or f"Outbound {c_type}", 
                "subtitle": frappe.utils.strip_html_tags(c["content"])[:150]
            })

        # 3. Loan Repayments
        lr = DocType("Loan Repayment")
        repayments = frappe.qb.from_(lr).select(
            lr.name.as_("id"), lr.posting_date, lr.creation.as_("timestamp"), lr.owner.as_("actor"),
            lr.amount_paid, lr.principal_amount_paid, lr.total_interest_paid, lr.total_penalty_paid
        ).where(
            (lr.against_loan == loan_id) & (lr.docstatus == 1)
        ).run(as_dict=True)

        for r in repayments:
            timeline.append({
                "id": r["id"], 
                "type": "system", 
                "timestamp": r["timestamp"], 
                "actor": r["actor"],
                "title": "Repayment processed", 
                "subtitle": f"K {r['amount_paid']:,.2f} received (Principal: K {r['principal_amount_paid']:,.2f}, Interest: K {r['total_interest_paid']:,.2f})"
            })

        # 4. Interest Accruals
        lia = DocType("Loan Interest Accrual")
        accruals = frappe.qb.from_(lia).select(
            lia.name.as_("id"), lia.posting_date, lia.creation.as_("timestamp"), lia.owner.as_("actor"),
            lia.interest_amount
        ).where(
            (lia.loan == loan_id) & (lia.docstatus == 1)
        ).run(as_dict=True)

        for a in accruals:
            if a.get("interest_amount"):
                timeline.append({
                    "id": f"{a['id']}_int", 
                    "type": "system", 
                    "timestamp": a["timestamp"], 
                    "actor": "System",
                    "title": "Interest accrued for the current cycle", 
                    "subtitle": f"K {a['interest_amount']:,.2f} posted to the loan ledger"
                })

        # 5. Schedule Changes / Restructures
        lrs = DocType("Loan Repayment Schedule")
        schedules = frappe.qb.from_(lrs).select(
            lrs.name.as_("id"), lrs.creation.as_("timestamp"), lrs.owner.as_("actor"), lrs.amended_from
        ).where(
            (lrs.loan == loan_id) & (lrs.docstatus == 1)
        ).run(as_dict=True)

        for s in schedules:
            is_restructure = bool(s["amended_from"])
            timeline.append({
                "id": s["id"], 
                "type": "system", 
                "timestamp": s["timestamp"], 
                "actor": s["actor"],
                "title": "Loan restructured" if is_restructure else "Initial Repayment Schedule Generated", 
                "subtitle": f"Schedule reference: {s['id']}"
            })

        # 6. System Versions (General edits & Status Changes)
        version = DocType("Version")
        versions = frappe.qb.from_(version).select(
            version.name.as_("id"), version.creation.as_("timestamp"), 
            version.owner.as_("actor"), version.data
        ).where(
            (version.ref_doctype == "Loan") & (version.docname == loan_id)
        ).run(as_dict=True)

        for v in versions:
            parsed_data = frappe.parse_json(v["data"] or "{}")
            changed_fields = [c[0] for c in parsed_data.get("changed", [])]
            
            # Filter out noisy background updates and only log meaningful changes
            if changed_fields and not all(f in ["modified", "docstatus"] for f in changed_fields):
                timeline.append({
                    "id": v["id"], 
                    "type": "system", 
                    "timestamp": v["timestamp"], 
                    "actor": v["actor"],
                    "title": "Account reviewed / updated", 
                    "subtitle": f"Updated fields: {', '.join(changed_fields)}"
                })

        # Sort the entire unified timeline descending by timestamp
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)

        return timeline

    except frappe.DoesNotExistError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan View: Audit Trail Error")
        raise frappe.ValidationError(f"Failed to fetch audit trail: {str(e)}")