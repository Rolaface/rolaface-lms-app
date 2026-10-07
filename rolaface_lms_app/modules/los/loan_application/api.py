import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER


@frappe.whitelist(methods=["POST"])
def create_loan_application():
	"""
	Create LOS Loan Application
	---
	tags:
	  - LOS Loan Application
	summary: Saves a complete application as a Draft, in the Application stage.
	description: >
	  Individual applications need next of kin, employment and a Current address. Business applications need
	  the business details (with position, PACRA number and TPIN), at least one director and an Office address;
	  next of kin and employment are not used. company is optional and defaults to the default company.
	  loan_product, stage, custom_status and the stage data are set by the pipeline, not here.
	requestBody:
	  required: true
	  content:
	    application/json:
	      examples:
	        individual:
	          summary: Individual (vehicle loan)
	          value: {"channel": "Branch", "customer_type": "New", "applicant_type": "Individual", "loan_type": "8pejo3vq5o", "loan_sub_type": "8peugt6t79", "loan_purpose": "8pe7b4vm6m", "requested_amount": 35000, "tenure_months": 18, "repayment_frequency": "Monthly", "first_name": "Chanda", "last_name": "Mwansa", "nrc": "123456/78/1", "phone": "+260977123456", "email": "chanda.mwansa@example.com", "gender": "Female", "marital_status": "Married", "date_of_birth": "1990-03-14", "nationality": "Zambia", "credit_score": 712, "kin_name": "Mwansa Mwansa", "kin_phone": "+260977456789", "kin_email": "mwansa.mwansa@example.com", "kin_relationship": "Spouse", "employment_status": "Salaried", "employment_type": "Government", "employer_name": "Ministry of Health", "designation": "Senior Nurse", "experience_years": 8, "financials": {"income": [{"source": "Net Salary", "monthly_amount": 18500}, {"source": "Rental Income", "monthly_amount": 2500}], "obligations": [{"source": "Monthly Obligation", "monthly_amount": 3200}], "expenses": [{"source": "Household", "monthly_amount": 4000}, {"source": "Education", "monthly_amount": 1500}]}, "collaterals": [{"collateral_type": "Vehicle", "estimated_value": 42000, "ownership_date": "2021-06-15", "description": "Toyota Corolla 2019, ABC 1234"}], "documents": [{"document_name": "Latest three payslips", "file": "/files/payslips.pdf"}, {"document_name": "NRC copy", "file": "/files/nrc-copy.jpg"}], "addresses": [{"address_type": "Current", "address_line1": "Plot 22, Kabulonga Road", "city": "Lusaka", "state": "Lusaka", "country": "Zambia", "pincode": "10101"}, {"address_type": "Permanent", "address_line1": "House 14, Mpatamatu", "city": "Luanshya", "state": "Copperbelt", "country": "Zambia"}]}
	        business:
	          summary: Business (working capital)
	          value: {"channel": "Branch", "customer_type": "New", "applicant_type": "Business", "loan_type": "nopda0pc2r", "loan_sub_type": "nopbd7f29q", "loan_purpose": "nopbjnqr9s", "requested_amount": 80000, "tenure_months": 24, "repayment_frequency": "Monthly", "first_name": "Bwalya", "last_name": "Phiri", "nrc": "234567/11/2", "phone": "+260966552310", "email": "bwalya.phiri@example.com", "gender": "Male", "marital_status": "Single", "date_of_birth": "1985-07-02", "nationality": "Zambia", "credit_score": 688, "position": "Managing Director", "company_name": "Kalingalinga Traders Ltd", "registration_number": "120150001234", "tpin": "1002345678", "business_type": "Private Limited Company", "established_date": "2015-01-12", "nature_of_business": "Wholesale of building materials", "directors": [{"full_name": "Bwalya Phiri", "nrc": "234567/11/2", "phone": "+260966552310", "email": "bwalya.phiri@example.com"}, {"full_name": "Mutale Banda", "nrc": "345678/22/1", "phone": "+260955903217", "email": "mutale.banda@example.com"}], "financials": {"income": [{"source": "Business Income", "monthly_amount": 65000}], "obligations": [{"source": "Other Monthly Debt", "monthly_amount": 8000}], "expenses": []}, "collaterals": [{"collateral_type": "Vehicle", "estimated_value": 95000, "ownership_date": "2020-02-01", "description": "Isuzu delivery truck, ALB 4521"}], "documents": [{"document_name": "PACRA certificate", "file": "/files/pacra-certificate.pdf"}, {"document_name": "Board resolution", "file": "/files/board-resolution.pdf"}, {"document_name": "NRC - Mutale Banda", "file": "/files/nrc-mutale-banda.jpg"}], "addresses": [{"address_type": "Office", "address_line1": "Plot 9, Roma Industrial Area", "city": "Lusaka", "state": "Lusaka", "country": "Zambia"}, {"address_type": "Current", "address_line1": "House 4B, Chilenje", "city": "Lusaka", "country": "Zambia"}]}
	      schema:
	        type: object
	        required: [channel, customer_type, applicant_type, loan_type, loan_sub_type, loan_purpose, requested_amount, tenure_months, first_name, last_name, nrc, phone, email, gender, marital_status, date_of_birth, nationality, credit_score, addresses]
	        properties:
	          application_date: {type: string, format: date, description: Defaults to today. Not in the future.}
	          company: {type: string, description: Defaults to the default company.}
	          channel: {type: string, description: An active channel.}
	          customer_type: {type: string, enum: [New, Existing]}
	          customer: {type: string, description: Required when customer_type is Existing.}
	          applicant_type: {type: string, enum: [Individual, Business]}
	          loan_type: {type: string, description: Loan type tree ID (level 1) for this applicant type.}
	          loan_sub_type: {type: string, description: Sub-type ID under loan_type.}
	          loan_purpose: {type: string, description: Purpose ID under loan_sub_type.}
	          requested_amount: {type: number}
	          tenure_months: {type: integer}
	          repayment_frequency: {type: string, enum: [Monthly, Bi-weekly], default: Monthly}
	          first_name: {type: string}
	          middle_name: {type: string}
	          last_name: {type: string}
	          nrc: {type: string}
	          phone: {type: string}
	          email: {type: string}
	          gender: {type: string, enum: [Male, Female, Other]}
	          marital_status: {type: string, enum: [Single, Married, Divorced, Widowed, Separated]}
	          date_of_birth: {type: string, format: date}
	          nationality: {type: string, description: Country name.}
	          credit_score: {type: integer, description: 300-850.}
	          position: {type: string, description: Business only.}
	          company_name: {type: string, description: Business only.}
	          registration_number: {type: string, description: Business only (PACRA).}
	          tpin: {type: string, description: Business only.}
	          business_type: {type: string, enum: [Sole Proprietorship, Partnership, Private Limited Company, Public Limited Company, Cooperative, Other], description: Business only.}
	          established_date: {type: string, format: date, description: Business only.}
	          nature_of_business: {type: string, description: Business only.}
	          kin_name: {type: string, description: Individual only.}
	          kin_phone: {type: string, description: Individual only.}
	          kin_email: {type: string, description: Individual only.}
	          kin_relationship: {type: string, enum: [Spouse, Parent, Sibling, Child, Grandparent, Grandchild, Uncle/Aunt, Nephew/Niece, Cousin, Guardian, Friend, Other], description: Individual only.}
	          employment_status: {type: string, enum: [Salaried, Self Employed, Pensioner, Others], description: Individual only.}
	          employment_type: {type: string, enum: [Government, Private, Self-Employed, Others], description: Individual only.}
	          employer_name: {type: string, description: Individual only.}
	          designation: {type: string, description: Individual only.}
	          experience_years: {type: number, description: Individual only.}
	          financials: {type: object, description: '{income, obligations, expenses}: each a list of {source, monthly_amount}.'}
	          directors: {type: array, items: {type: object}, description: 'Business only. [{full_name, nrc, phone, email}]'}
	          collaterals: {type: array, items: {type: object}, description: '[{collateral_type, estimated_value, ownership_date, description}]. collateral_type is a Loan Security Type.'}
	          documents: {type: array, items: {type: object}, description: '[{document_name, file}]. file is the URL from Frappe file upload.'}
	          addresses: {type: array, items: {type: object}, description: '[{address_type (Current, Permanent or Office), address_line1, address_line2, city, state, country, pincode}]'}
	responses:
	  201:
	    description: Application created as a Draft.
	"""
	try:
		result = service.create_loan_application(request_args())
		frappe.db.commit()
		return send_response("success", "Loan application created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Loan Application API Error")


@frappe.whitelist(methods=["PUT"])
def update_loan_application(id=None):
	"""
	Update LOS Loan Application
	---
	tags:
	  - LOS Loan Application
	summary: One update for every stage modal. Send only what changed; fields left out are kept.
	description: >
	  Nothing can change once the application is Approved, Rejected or Cancelled (409). Application details (any
	  create_loan_application field) may be sent in any open stage; a list sent (directors, collaterals, documents, addresses) replaces that whole list, and the result must
	  still be a complete application. Collateral rows sent with their row_id are updated in place (valuation fields
	  are kept unless sent), rows without row_id are added, and rows left out are removed; a collateral row may also
	  carry valuation_amount, forced_sale_value, valuation_status, legal_status and valuation_details. Stage fields -
	  custom_status (the status within the current workflow stage); pre-screening:
	  monthly_income, monthly_obligations, eligible_amount, prescreening_data; appraisal: approved_amount,
	  approved_tenure_months, approved_frequency, interest_rate, appraisal_data; underwriting: final_amount,
	  underwriting_decision, underwriting_data, collateral_valuations; offer: signing_method, contract_status,
	  first_payment_date, offer_data.
	  collateral_valuations updates collateral rows by row_id (from get_loan_application_by_id) and only changes
	  the valuation fields sent. Send null to clear a field. status, stage and workflow_state are not sent here.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      examples:
	        application:
	          summary: Application details
	          value: {"requested_amount": 30000, "tenure_months": 24, "collaterals": [{"collateral_type": "Vehicle", "estimated_value": 40000, "ownership_date": "2021-06-15", "description": "Toyota Corolla 2019, ABC 1234"}]}
	        prescreening:
	          summary: Pre-screening
	          value: {"monthly_obligations": 1200, "eligible_amount": 30000, "prescreening_data": {"bureau": {"risk_band": "Low", "active_accounts": 2, "delinquent_accounts": 0, "recent_enquiries": 1, "source": "bureau"}, "liabilities": [{"institution": "Zanaco", "facility_type": "Personal Loan", "outstanding": 12500, "monthly_payment": 850, "status": "Active", "source": "bureau"}], "income": [{"source": "Net Salary", "monthly_amount": 13100, "source_kind": "hrms"}]}}
	        appraisal:
	          summary: Appraisal
	          value: {"approved_amount": 30000, "approved_tenure_months": 18, "approved_frequency": "Monthly", "interest_rate": 22, "appraisal_data": {"interest_type": "Fixed", "interest_calculation": "Reducing Balance", "effective_date": "2026-10-10", "override_reason": null, "charges": [{"name": "Processing Fee", "basis": "%", "value": 2, "account": "Processing Fee Income", "treatment": "Deduct from disbursement"}]}}
	        underwriting:
	          summary: Underwriting
	          value: {"final_amount": 30000, "underwriting_decision": "Approved with Conditions", "collateral_valuations": [{"row_id": "<row_id from get_loan_application_by_id>", "valuation_amount": 38000, "forced_sale_value": 30000, "valuation_status": "Passed", "legal_status": "Passed", "valuation_details": {"method": "Market comparison", "market_value": 40000, "valuation_date": "2026-10-08", "valuer": {"name": "A. Banda", "company": "Banda Valuers", "license": "VAL-221"}}}], "underwriting_data": {"conditions": [{"condition": "Comprehensive insurance on vehicle", "responsible": "Customer", "due_before": "Disbursement"}], "notes": "Stable salaried applicant."}}
	        offer:
	          summary: Offer & Signing
	          value: {"signing_method": "E-signature", "first_payment_date": "2026-11-30", "offer_data": {"dispatch_status": "Dispatched", "signed_copy_received": false}}
	      schema:
	        type: object
	        properties:
	          custom_status: {type: string, description: Status within the current workflow stage.}
	          monthly_income: {type: number}
	          monthly_obligations: {type: number}
	          eligible_amount: {type: number}
	          prescreening_data: {type: object}
	          approved_amount: {type: number}
	          approved_tenure_months: {type: integer}
	          approved_frequency: {type: string, enum: [Monthly, Bi-weekly]}
	          interest_rate: {type: number}
	          appraisal_data: {type: object}
	          final_amount: {type: number}
	          underwriting_decision: {type: string, enum: [Approved, Approved with Conditions, Referred, Rejected]}
	          underwriting_data: {type: object}
	          collateral_valuations: {type: array, items: {type: object}, description: '[{row_id, valuation_amount, forced_sale_value, valuation_status (Pending, Passed, Failed, Exception), legal_status (Pending, Passed, Unresolved), valuation_details}]'}
	          signing_method: {type: string, enum: [E-signature, Physical Signature]}
	          contract_status: {type: string, enum: [Not Generated, Signing in Progress, Executed]}
	          first_payment_date: {type: string, format: date}
	          offer_data: {type: object}
	responses:
	  400:
	    description: Nothing to update, a field that cannot be sent here, an unknown collateral row_id, or invalid values.
	  409:
	    description: The application is Approved, Rejected or Cancelled.
	"""
	try:
		result = service.update_loan_application(require_id(id, "Loan Application"), request_args())
		frappe.db.commit()
		return send_response("success", "Loan application updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Loan Application API Error")


@frappe.whitelist(methods=["GET"])
def get_loan_application_by_id(id=None):
	"""
	Get LOS Loan Application By ID
	---
	tags:
	  - LOS Loan Application
	summary: The whole application, including directors, collaterals, documents, addresses and every stage's data.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	"""
	try:
		result = service.get_loan_application_by_id(require_id(id, "Loan Application"))
		return send_response("success", "Loan application retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Loan Application By ID Error")


@frappe.whitelist(methods=["GET"])
def get_loan_applications(page=1, page_size=20):
	"""
	List LOS Loan Applications
	---
	tags:
	  - LOS Loan Application
	summary: One list for every origination screen. Filter by workflow_state (and custom_status) for each origination stage screen.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches application ID / applicant name / company name / NRC / phone, schema: {type: string}}
	  - {in: query, name: status, schema: {type: string, enum: [Draft, Submitted, Approved, Rejected, Cancelled]}}
	  - {in: query, name: workflow_state, description: Current workflow stage (e.g. Draft, Pre-Screening, Appraisal, Underwriting, Offer), schema: {type: string}}
	  - {in: query, name: stage, schema: {type: string, enum: [Application, Pre-screening, Appraisal, Underwriting, Offer, Booked]}}
	  - {in: query, name: applicant_type, schema: {type: string, enum: [Individual, Business]}}
	  - {in: query, name: channel, schema: {type: string}}
	  - {in: query, name: customer, schema: {type: string}}
	  - {in: query, name: loan_product, schema: {type: string}}
	  - {in: query, name: custom_status, description: Status within the current workflow stage, schema: {type: string}}
	  - {in: query, name: from_date, description: Application date from, schema: {type: string, format: date}}
	  - {in: query, name: to_date, description: Application date to, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [modified, creation, application_date, requested_amount, name], default: modified}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: desc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records = service.get_loan_applications(
			args=args,
			page=page,
			page_size=page_size,
			sort_by=args.get("sort_by") or DEFAULT_SORT_BY,
			sort_order=args.get("sort_order") or DEFAULT_SORT_ORDER,
		)
		return send_response_list(
			"success",
			"Loan applications retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get All LOS Loan Applications Error")


@frappe.whitelist(methods=["DELETE"])
def delete_loan_application(id=None):
	"""
	Delete LOS Loan Application
	---
	tags:
	  - LOS Loan Application
	summary: Deletes a Draft application and its addresses. Submitted applications are kept.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	responses:
	  409:
	    description: The application is no longer a Draft.
	"""
	try:
		service.delete_loan_application(require_id(id, "Loan Application"))
		frappe.db.commit()
		return send_response("success", "Loan application deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Loan Application Error")
