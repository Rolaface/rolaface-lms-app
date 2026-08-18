import frappe
from apps.lending.lending.loan_management.doctype.loan_repayment.loan_repayment import calculate_amounts

def validate_payload(payload):
    against_loan = payload.get("against_loan")
    payment_type=payload.get("repayment_type")
    value_date=payload.get("value_date")

    amounts = calculate_amounts(against_loan=against_loan, payment_type=payment_type, posting_date=value_date)
    frappe.log_error(f"Amounts --> {amounts}")
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
