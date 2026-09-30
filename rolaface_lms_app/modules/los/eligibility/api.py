import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service

# ---------------------------------------------------------------- Reads


@frappe.whitelist(methods=["GET"])
def get_eligibility_rules(page=1, page_size=20):
	"""
	List Eligibility Rules
	---
	tags:
	  - LOS Eligibility
	summary: One line per loan product, showing its live version (else its draft), with draft_id (the unpublished draft behind the live version, null if none).
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches rule name or loan product, schema: {type: string}}
	  - {in: query, name: status, schema: {type: string, enum: [Draft, Active, Inactive]}}
	  - {in: query, name: loan_product, schema: {type: string}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records = service.get_eligibility_rules(args, page, page_size)
		return send_response_list(
			"success",
			"Eligibility rules retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get LOS Eligibility Rules Error")


@frappe.whitelist(methods=["GET"])
def get_eligibility_rule(id=None):
	"""
	Get Eligibility Rule
	---
	tags:
	  - LOS Eligibility
	summary: One version with all its configuration sections, and draft_id if another version is the product's draft.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	"""
	try:
		result = service.get_eligibility_rule(require_id(id, "Eligibility Rule"))
		return send_response("success", "Eligibility rule retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Eligibility Rule Error")


@frappe.whitelist(methods=["GET"])
def get_eligibility_rule_versions(loan_product=None):
	"""
	Eligibility Rule Versions
	---
	tags:
	  - LOS Eligibility
	summary: Every version of a loan product's eligibility rule, newest first.
	parameters:
	  - {in: query, name: loan_product, required: true, schema: {type: string}}
	"""
	try:
		result = service.get_eligibility_rule_versions(request_args().get("loan_product") or loan_product)
		return send_response_list("success", "Eligibility rule versions retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Eligibility Rule Versions Error")


# ---------------------------------------------------------------- Writes

@frappe.whitelist(methods=["POST"])
def create_eligibility_rule():
	"""
	Create Eligibility Rule
	---
	tags:
	  - LOS Eligibility
	summary: New eligibility rule for a loan product, as version 1.0 Draft. One rule per loan product.
	description: Only rule_name and loan_product are required. Every section is optional and can be filled later with update_eligibility_rule.
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required: [rule_name, loan_product]
	        properties:
	          rule_name: {type: string}
	          loan_product: {type: string}
	          effective_from: {type: string, format: date, description: Optional. Defaults to the activation day.}
	          effective_to: {type: string, format: date, description: Optional. Not before effective_from.}
	          income_sources: {type: array, items: {type: object}, description: '[{name, recognition_pct, verification_required, included}]'}
	          obligation_sources: {type: array, items: {type: object}, description: '[{name, pct, verification_required, included}]'}
	          credit_bands: {type: array, items: {type: object}, description: '[{grade, min_score, multiple, basis, decision}]'}
	          internal_bands: {type: array, items: {type: object}, description: '[{grade, min_score, multiple, basis, decision}]'}
	          collateral_items: {type: array, items: {type: object}, description: '[{type, haircut_pct, max_ltv_pct}]. Other keys are dropped.'}
	          formula_params: {type: object, description: '{other_income_recognition, salary_multiple, max_emi_ratio, max_dti_ratio, affordability_buffer, product_max}. Other keys are dropped.'}
	          hard_stops: {type: array, items: {type: object}, description: Saved as sent for now.}
	          manual_reviews: {type: array, items: {type: object}, description: Saved as sent for now.}
	responses:
	  201:
	    description: Rule created as a draft.
	  409:
	    description: The loan product already has an eligibility rule.
	"""
	try:
		result = service.create_eligibility_rule(request_args())
		frappe.db.commit()
		return send_response("success", "Eligibility rule created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Eligibility Rule API Error")


@frappe.whitelist(methods=["PUT"])
def update_eligibility_rule(id=None):
	"""
	Update Eligibility Rule (Save Draft)
	---
	tags:
	  - LOS Eligibility
	summary: Saves changes into the product's draft. Editing a published version creates the draft from it first; live applications are not affected until activation.
	description: Send only what changed; a section sent replaces that section, sections left out are kept. The response is the draft, so use its name from then on.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        properties:
	          rule_name: {type: string}
	          effective_from: {type: string, format: date}
	          effective_to: {type: string, format: date}
	          income_sources: {type: array, items: {type: object}, description: '[{name, recognition_pct, verification_required, included}]'}
	          obligation_sources: {type: array, items: {type: object}, description: '[{name, pct, verification_required, included}]'}
	          credit_bands: {type: array, items: {type: object}, description: '[{grade, min_score, multiple, basis, decision}]'}
	          internal_bands: {type: array, items: {type: object}, description: '[{grade, min_score, multiple, basis, decision}]'}
	          collateral_items: {type: array, items: {type: object}, description: '[{type, haircut_pct, max_ltv_pct}]. Other keys are dropped.'}
	          formula_params: {type: object, description: '{other_income_recognition, salary_multiple, max_emi_ratio, max_dti_ratio, affordability_buffer, product_max}. Other keys are dropped.'}
	          hard_stops: {type: array, items: {type: object}, description: Saved as sent for now.}
	          manual_reviews: {type: array, items: {type: object}, description: Saved as sent for now.}
	responses:
	  400:
	    description: Nothing to update, an archived version, status / version / loan_product sent, a bad date, or a section of the wrong type.
	"""
	try:
		result = service.update_eligibility_rule(require_id(id, "Eligibility Rule"), request_args())
		frappe.db.commit()
		return send_response("success", "Eligibility rule saved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Eligibility Rule API Error")


@frappe.whitelist(methods=["PUT"])
def set_eligibility_rule_status(id=None):
	"""
	Set Eligibility Rule Status
	---
	tags:
	  - LOS Eligibility
	summary: Active publishes a draft (or switches an inactive version back on); Inactive switches the active version off.
	description: >
	  The previous version is archived. Effective From defaults to today if empty, and the archived
	  version's Effective To defaults to today if empty.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required: [status]
	        properties:
	          status: {type: string, enum: [Active, Inactive]}
	responses:
	  400:
	    description: Invalid status, already in that status, or this version cannot take it.
	"""
	try:
		args = request_args()
		result = service.set_eligibility_rule_status(require_id(id, "Eligibility Rule"), args.get("status"))
		frappe.db.commit()
		return send_response("success", f"Eligibility rule is now {result['status'].lower()}.", result)
	except Exception as e:
		return handle_api_error(e, "Set LOS Eligibility Rule Status API Error")


@frappe.whitelist(methods=["DELETE"])
def delete_eligibility_rule(id=None):
	"""
	Delete Eligibility Rule Version
	---
	tags:
	  - LOS Eligibility
	summary: Deletes a draft. Versions that have been live are kept as history.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	responses:
	  409:
	    description: The version has been live. Deactivate it instead.
	"""
	try:
		service.delete_eligibility_rule(require_id(id, "Eligibility Rule"))
		frappe.db.commit()
		return send_response("success", "Eligibility rule version deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Eligibility Rule API Error")
