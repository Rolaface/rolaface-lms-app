import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response

from ..common import parse_flag, request_args
from .pipeline import evaluate_application as evaluate, test_eligibility, test_prescreening
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


@frappe.whitelist(methods=["POST"])
def evaluate_application():
	"""
	Evaluate Application
	---
	tags:
	  - LOS Engine
	summary: Runs pre-screening and then eligibility on a loan application.
	description: >
	  Uses the application's loan product and that product's Active pre-screening rule set and eligibility rule
	  (effective today). Eligibility is skipped when pre-screening is Not Eligible. A product without an active rule
	  set or rule gives Manual Review with the reason. verdict is the worst of the two results (Not Eligible >
	  Manual Review > Eligible with Warnings > Eligible).

	  overrides are the officer's figures from the Pre-screening screen: credit_score, requested_amount, income and
	  obligations (each a list of {source, monthly_amount} that replaces the application's lines). With save=1
	  (only while the application is in Pre-Screening) the result is stored in prescreening_data.engine,
	  eligible_amount is updated and custom_status becomes the stage status (the officer's Save). With approve=1 the
	  same is stored but custom_status becomes Approved (the officer's decision; without overrides it reuses the officer's
	  last saved figures, so the list's Approve matches what the screen showed); it is refused for a Fail result and
	  for a Pass / Warning whose requested amount is above the eligible amount. The workflow actions Submit for Pre-Screening and Return (when the application lands
	  in Pre-Screening) run this automatically with save and set custom_status to the stage status: Pass (Eligible),
	  Warning (Eligible with Warnings), Review (Manual Review) or Fail (Not Eligible).
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"application": "LA-2026-00047", "overrides": {"credit_score": 720, "requested_amount": 50000, "income": [{"source": "Net Salary", "monthly_amount": 18500}], "obligations": [{"source": "Monthly Obligation", "monthly_amount": 2500}]}, "save": 0, "approve": 0}
	responses:
	  400:
	    description: Invalid overrides, save outside Pre-Screening, or an approval the result does not allow.
	  404:
	    description: The application does not exist.
	"""
	try:
		args = request_args()
		result = evaluate(
			args.get("application"),
			args.get("overrides"),
			parse_flag(args.get("save") or 0, "save"),
			approve=parse_flag(args.get("approve") or 0, "approve"),
		)
		return send_response("success", "Application evaluated.", result)
	except Exception as e:
		return handle_api_error(e, "LOS Evaluate Application Error")


@frappe.whitelist(methods=["POST"])
def run_prescreening():
	"""
	Run Pre-screening
	---
	tags:
	  - LOS Engine
	summary: Runs only the pre-screening rules (for testing).
	description: >
	  Send application (an application ID) or data (application fields in the create_loan_application shape).
	  loan_product defaults to the application's. Uses the product's Active rule set; nothing is saved. A rule whose
	  value is missing fails at its own severity.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"loan_product": "PL-PAY", "data": {"date_of_birth": "1985-06-01", "nationality": "Zambia", "employment_status": "Salaried", "employment_type": "Government", "credit_score": 690, "requested_amount": 120000, "tenure_months": 36, "financials": {"income": [{"source": "Net Salary", "monthly_amount": 21000}], "obligations": [{"source": "Monthly Obligation", "monthly_amount": 3000}]}}}
	responses:
	  400:
	    description: Missing or unknown loan product, or no application data.
	"""
	try:
		return send_response("success", "Pre-screening evaluated.", test_prescreening(request_args()))
	except Exception as e:
		return handle_api_error(e, "LOS Run Pre-screening Error")


@frappe.whitelist(methods=["POST"])
def run_eligibility():
	"""
	Run Eligibility
	---
	tags:
	  - LOS Engine
	summary: Runs only the eligibility rule (for testing).
	description: >
	  Same input as run_prescreening. Returns the eligible amount (the lowest of the income, affordability, credit,
	  collateral and product limits), the limiting factor, each limit with its inputs, the credit band, debt service
	  and EMI-to-income ratios, the decision (Eligible / Manual Review / Not Eligible) with reasons, and the hard-stop
	  and manual-review rules that could not be checked for lack of data. Nothing is saved.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"application": "LA-2026-00047"}
	responses:
	  400:
	    description: Missing or unknown loan product, or no application data.
	"""
	try:
		return send_response("success", "Eligibility evaluated.", test_eligibility(request_args()))
	except Exception as e:
		return handle_api_error(e, "LOS Run Eligibility Error")
