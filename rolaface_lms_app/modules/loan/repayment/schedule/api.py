import frappe
from frappe import _
from frappe.utils import flt, getdate
from .service import get_fixed_repayment_schedule

@frappe.whitelist(allow_guest=False, methods=["GET"])
def calculate_fixed_amount_schedule(loan_amount: float, rate_of_interest: float, monthly_repayment_amount: float, repayment_frequency: str, repayment_start_date: str = None) -> list[dict]:

    schedule = get_fixed_repayment_schedule(loan_amount, rate_of_interest, monthly_repayment_amount, repayment_frequency, repayment_start_date)

    frappe.response["message"] = schedule

# def calculate_fixed_amount_schedule(loan_product: str, loan_amount: float, rate_of_interest: float, monthly_repayment_amount: int, repayment_frequency: str | None, repayment_start_date: str | None = None) -> list[dict]:
# 	"""
# 	API to get the repayment schedule for given loan product and repayment frequency
# 	"""

# 	repayment_schedule = frappe.new_doc("Loan Repayment Schedule")
# 	repayment_schedule.loan_product = loan_product
# 	repayment_schedule.repayment_frequency = repayment_frequency or "Monthly"
# 	repayment_schedule.repayment_method = "Repay Fixed Amount per Period"
# 	# repayment_schedule.repayment_periods = tenure
# 	repayment_schedule.monthly_repayment_amount = monthly_repayment_amount
# 	repayment_schedule.rate_of_interest = rate_of_interest
# 	repayment_schedule.posting_date = getdate()
# 	repayment_schedule.repayment_start_date = getdate(repayment_start_date)
# 	repayment_schedule.loan_amount = loan_amount
# 	repayment_schedule.current_principal_amount = loan_amount
# 	repayment_schedule.moratorium_tenure = 0
# 	repayment_schedule.moratorium_type = ""

# 	repayment_schedule.repayment_schedule_type = frappe.db.get_value("Loan Product", loan_product, "repayment_schedule_type")
# 	repayment_schedule.validate()

# 	response = {
# 		"loan_amount": repayment_schedule.loan_amount,
# 		"rate_of_interest": repayment_schedule.rate_of_interest,
# 		"monthly_repayment_amount": repayment_schedule.monthly_repayment_amount,
# 		"repayment_start_date": repayment_schedule.repayment_start_date,
# 		"repayment_periods": []
# 	}

# 	for row in repayment_schedule.get("repayment_schedule"):
# 		response["repayment_periods"].append({
# 			"payment_date": row.payment_date,
# 			"principal_amount": flt(row.principal_amount, 2),
# 			"interest_amount": flt(row.interest_amount, 2),
# 			"total_payment": flt(row.total_payment, 2),
# 			"balance_loan_amount": flt(row.balance_loan_amount, 2)
# 		})

# 	frappe.response["message"] = response