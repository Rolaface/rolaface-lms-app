import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response

from ..common import request_args
from .product_assignment import assign_product


@frappe.whitelist(methods=["POST"])
def assign_loan_product():
	"""
	Assign Loan Product
	---
	tags:
	  - LOS Engine
	summary: Runs the product assignment rules on an application that is being filled in.
	description: >
	  Send the application as entered so far (the create_loan_application shape; loan_type is required, channel
	  defaults to Branch). The rules of that channel and loan type are evaluated against the application's fields.
	  status is Rule matched, Loan type default, Manual review (no rule and no default product) or Conflict (more
	  than one rule matches). For an assigned product the response also carries its interest rate, maximum loan
	  amount and its documents from Document Setup (null when the product has no setup). Nothing is saved; saving
	  the application assigns the product again on the server.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"channel": "Branch", "applicant_type": "Individual", "loan_type": "pmv0rb831q", "loan_sub_type": "8pe6ssf2rf", "requested_amount": 45000, "tenure_months": 18, "credit_score": 712, "date_of_birth": "1990-03-14", "nationality": "Zambia", "employment_status": "Salaried", "financials": {"income": [{"source": "Net Salary", "monthly_amount": 18500}], "obligations": []}}
	responses:
	  400:
	    description: loan_type is missing.
	"""
	try:
		result = assign_product(request_args())
		return send_response("success", "Loan product assignment evaluated.", result)
	except Exception as e:
		return handle_api_error(e, "LOS Assign Loan Product Error")
