import frappe
from frappe.utils import flt
from lending.loan_management.doctype.loan_repayment.loan_repayment import calculate_amounts

def validate_payload(payload):
    against_loan = payload.get("against_loan")
    payment_type=payload.get("repayment_type")
    value_date=payload.get("value_date")
    frappe.log_error(f"against_loan --> {against_loan}, payment_type --> {payment_type}, value_date --> {value_date}")

    amounts = calculate_amounts(against_loan=against_loan, payment_type=payment_type, posting_date=value_date)
    frappe.log_error(f"Amounts --> {amounts}")

    total_outstanding_amount = (
        flt(amounts.get("pending_principal_amount"))
        + flt(amounts.get("interest_amount"))
        + flt(amounts.get("penalty_amount"))
        # + flt(amounts.get("unaccrued_interest"))
        # + flt(amounts.get("unbooked_interest"))
        # + flt(amounts.get("unbooked_penalty"))
        + flt(amounts.get("total_charges_payable"))
    )

    if float(payload.get("amount_paid")) > total_outstanding_amount:
        frappe.throw(
            "The amount paid cannot be greater than the total outstanding amount on the loan."
        )

    if payload.get("repayment_type") == "Normal Repayment" and float(payload.get("amount_paid")) > float(amounts.get("payable_amount")):
        frappe.throw(
                        "The amount paid exceeds the outstanding due amount. "
                        "Please use the Pre-Payment option for payments exceeding the due amount."
                    )

    if payload.get("repayment_type") == "Pre Payment" and float(payload.get("amount_paid")) < float(amounts.get("payable_amount")):
         frappe.throw(
                        "The amount paid is less than the outstanding due amount. "
                        "Please use the Pay Due option to settle the outstanding amount."
                    )
