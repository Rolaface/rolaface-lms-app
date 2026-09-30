import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service

GROUPS_DESCRIPTION = (
	"[{id, name, logic: ALL|ANY, rules: [{id, field, operator, value, value2, values, date_unit, severity, action, disabled}]}]. "
	"Fields, operators, severities and actions come from get_prescreening_fields."
)

# ---------------------------------------------------------------- Reads


@frappe.whitelist(methods=["GET"])
def get_rulesets(page=1, page_size=20):
	"""
	List Pre-Screening Rule Sets
	---
	tags:
	  - LOS Pre-Screening
	summary: One line per loan product, showing its live version (else its draft), with rules_count and the draft ID if there is one.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches rule set name or loan product, schema: {type: string}}
	  - {in: query, name: status, schema: {type: string, enum: [Draft, Active, Inactive]}}
	  - {in: query, name: loan_product, schema: {type: string}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records = service.get_rulesets(args, page, page_size)
		return send_response_list(
			"success",
			"Pre-screening rule sets retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get LOS Pre-Screening Rule Sets Error")


@frappe.whitelist(methods=["GET"])
def get_ruleset(id=None):
	"""
	Get Pre-Screening Rule Set
	---
	tags:
	  - LOS Pre-Screening
	summary: One version with its rule groups. draft is the ID of the product's draft, if another version is shown.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	"""
	try:
		result = service.get_ruleset(require_id(id, "Rule Set"))
		return send_response("success", "Pre-screening rule set retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Pre-Screening Rule Set Error")


@frappe.whitelist(methods=["GET"])
def get_ruleset_versions(loan_product=None):
	"""
	Pre-Screening Rule Set Versions
	---
	tags:
	  - LOS Pre-Screening
	summary: Every version of a loan product's rule set, newest first (Versions tab).
	parameters:
	  - {in: query, name: loan_product, required: true, schema: {type: string}}
	"""
	try:
		loan_product = request_args().get("loan_product") or loan_product
		if not loan_product:
			raise frappe.ValidationError("loan_product is required.")
		result = service.get_ruleset_versions(loan_product)
		return send_response_list("success", "Pre-screening rule set versions retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Pre-Screening Rule Set Versions Error")


@frappe.whitelist(methods=["GET"])
def get_prescreening_fields():
	"""
	Pre-Screening Fields
	---
	tags:
	  - LOS Pre-Screening
	summary: Fields, operators per field type, severities with their default action, actions and date units for the rule builder.
	"""
	try:
		return send_response("success", "Pre-screening fields retrieved successfully.", service.get_prescreening_fields())
	except Exception as e:
		return handle_api_error(e, "Get LOS Pre-Screening Fields Error")


@frappe.whitelist(methods=["POST"])
def test_ruleset(id=None):
	"""
	Test Pre-Screening Rule Set
	---
	tags:
	  - LOS Pre-Screening
	summary: Runs sample applicant values through a version (drafts too) and returns the verdict, each group and rule result, and the failed rules.
	description: >
	  Verdict is Not Eligible (a Blocking rule failed), Manual Review (a Review rule failed), Eligible with Warnings
	  (a Warning rule failed) or Eligible. A rule's passed is null when its field has no value or the rule is unfinished;
	  failures only count when their group fails. Disabled rules are skipped. Nothing is saved.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required: [facts]
	        properties:
	          facts:
	            type: object
	            description: Applicant values by field ID.
	            example: {"age": 25, "monthly_income": 12500, "employment_status": "Permanent", "has_previous_default": false}
	responses:
	  400:
	    description: facts is not an object, or a value has the wrong type (e.g. text for a number field).
	"""
	try:
		args = request_args()
		result = service.test_ruleset(require_id(id, "Rule Set"), args.get("facts"))
		return send_response("success", "Pre-screening rule set tested successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Test LOS Pre-Screening Rule Set Error")


# ---------------------------------------------------------------- Writes


@frappe.whitelist(methods=["POST"])
def create_ruleset():
	"""
	Create Pre-Screening Rule Set
	---
	tags:
	  - LOS Pre-Screening
	summary: New rule set for a loan product, as version 1.0 Draft. One rule set per loan product.
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required: [ruleset_name, loan_product]
	        properties:
	          ruleset_name: {type: string}
	          loan_product: {type: string}
	          description: {type: string}
	          groups: {type: array, items: {type: object}}
	responses:
	  201:
	    description: Rule set created as a draft.
	  409:
	    description: The loan product already has a rule set.
	"""
	try:
		result = service.create_ruleset(request_args())
		frappe.db.commit()
		return send_response("success", "Pre-screening rule set created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Pre-Screening Rule Set API Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def update_ruleset(id=None):
	"""
	Update Pre-Screening Rule Set (Save Draft)
	---
	tags:
	  - LOS Pre-Screening
	summary: Saves changes into the product's draft. Editing a published version creates the draft from it first; live applications are not affected until activation.
	description: Send only what changed. Unfinished rules are allowed in a draft. The response is the draft, so use its name from then on.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        properties:
	          ruleset_name: {type: string}
	          description: {type: string}
	          groups: {type: array, items: {type: object}}
	responses:
	  400:
	    description: Nothing to update, an archived version, status / version / loan_product / effective_from sent, or an invalid rule.
	"""
	try:
		result = service.update_ruleset(require_id(id, "Rule Set"), request_args())
		frappe.db.commit()
		return send_response("success", "Pre-screening rule set saved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Pre-Screening Rule Set API Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def set_ruleset_status(id=None):
	"""
	Set Pre-Screening Rule Set Status
	---
	tags:
	  - LOS Pre-Screening
	summary: Active publishes a draft (or switches an inactive version back on); Inactive switches the active version off.
	description: >
	  Publishing needs every rule complete. The draft goes live today (Effective From is set to today)
	  and the previous version is archived (Effective To is set to today).
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
	    description: Invalid status, already in that status, this version cannot take it, or a rule is incomplete.
	"""
	try:
		args = request_args()
		result = service.set_ruleset_status(require_id(id, "Rule Set"), args.get("status"))
		frappe.db.commit()
		return send_response("success", f"Pre-screening rule set is now {result['status'].lower()}.", result)
	except Exception as e:
		return handle_api_error(e, "Set LOS Pre-Screening Rule Set Status API Error")


@frappe.whitelist(methods=["DELETE"])
def delete_ruleset(id=None):
	"""
	Delete Pre-Screening Rule Set Version
	---
	tags:
	  - LOS Pre-Screening
	summary: Deletes a draft. Versions that have been live are kept as history.
	parameters:
	  - {in: query, name: id, required: true, schema: {type: string}}
	responses:
	  409:
	    description: The version has been live. Deactivate it instead.
	"""
	try:
		service.delete_ruleset(require_id(id, "Rule Set"))
		frappe.db.commit()
		return send_response("success", "Pre-screening rule set version deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Pre-Screening Rule Set API Error")
