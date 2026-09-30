import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import request_args, require_id
from . import service

# ---------------------------------------------------------------- CRUD


@frappe.whitelist(methods=["POST"])
def create_node():
	"""
	Create Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Create a loan type (no parent), a sub-type (parent is a loan type) or a purpose (parent is a sub-type).
	description: Level, applicant type (for children) and the stored loan type / sub-type are worked out from the parent.
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required:
	          - node_name
	        properties:
	          node_name:
	            type: string
	          parent_node:
	            type: string
	            description: Empty for a loan type.
	          applicant_type:
	            type: string
	            enum: [Individual, Business]
	            description: Required for a loan type. Copied from the parent otherwise.
	          is_active:
	            type: integer
	            enum: [0, 1]
	responses:
	  201:
	    description: Node created successfully.
	  409:
	    description: The same name already exists under this parent.
	"""
	try:
		result = service.create_node(request_args())
		frappe.db.commit()
		return send_response("success", "Loan type tree node created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Loan Type Tree Node API Error")


@frappe.whitelist(methods=["PUT"])
def update_node(id=None):
	"""
	Update Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Rename a node. Parent and applicant type cannot change; use enable_node / disable_node for status.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required:
	          - node_name
	        properties:
	          node_name:
	            type: string
	responses:
	  400:
	    description: Nothing to update, a blank name, is_active sent, or parent / applicant type changed.
	  409:
	    description: The same name already exists under this parent.
	"""
	try:
		result = service.update_node(require_id(id, "Node"), request_args())
		frappe.db.commit()
		return send_response("success", "Loan type tree node updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Loan Type Tree Node API Error")


@frappe.whitelist(methods=["GET"])
def get_node_by_id(id=None):
	"""
	Get Loan Type Tree Node By ID
	---
	tags:
	  - LOS Loan Type Tree
	summary: Node details with parent, loan type and sub-type names, child count, and (for loan types) product assignment usage.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.get_node_by_id(require_id(id, "Node"))
		return send_response("success", "Loan type tree node retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Loan Type Tree Node By ID Error")


@frappe.whitelist(methods=["DELETE"])
def delete_node(id=None):
	"""
	Delete Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Delete a node. Refused while it has children or product assignment uses it; disable it instead.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	responses:
	  409:
	    description: It has items under it, or product assignment or other records use it. Disable it instead.
	"""
	try:
		service.delete_node(require_id(id, "Node"))
		frappe.db.commit()
		return send_response("success", "Loan type tree node deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Loan Type Tree Node Error")


@frappe.whitelist(methods=["PUT"])
def enable_node(id=None):
	"""
	Enable Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Sets is_active to 1. The parent must be active.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	responses:
	  400:
	    description: Already active, or its parent is inactive.
	"""
	try:
		result = service.toggle_node_status(require_id(id, "Node"), is_active=1)
		frappe.db.commit()
		return send_response("success", "Loan type tree node enabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Enable LOS Loan Type Tree Node API Error")


@frappe.whitelist(methods=["PUT"])
def disable_node(id=None):
	"""
	Disable Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Sets is_active to 0 on the node and everything under it. descendants_disabled says how many were switched off with it.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	responses:
	  400:
	    description: Already inactive.
	"""
	try:
		result = service.toggle_node_status(require_id(id, "Node"), is_active=0)
		frappe.db.commit()
		return send_response("success", "Loan type tree node disabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Disable LOS Loan Type Tree Node API Error")


# ---------------------------------------------------------------- Lookups


@frappe.whitelist(methods=["GET"])
def get_loan_types(applicant_type=None, include_inactive=0):
	"""
	Loan Types
	---
	tags:
	  - LOS Loan Type Tree
	summary: Level 1 nodes, optionally for one applicant type. First dropdown of the loan application.
	parameters:
	  - {in: query, name: applicant_type, schema: {type: string, enum: [Individual, Business]}}
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
	"""
	try:
		args = request_args()
		result = service.get_loan_types(
			args.get("applicant_type") or applicant_type, args.get("include_inactive", include_inactive)
		)
		return send_response_list("success", "Loan types retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Loan Types Error")


@frappe.whitelist(methods=["GET"])
def get_sub_types(loan_type=None, include_inactive=0):
	"""
	Sub-types of a Loan Type
	---
	tags:
	  - LOS Loan Type Tree
	summary: Level 2 nodes under one loan type. Second dropdown of the loan application.
	parameters:
	  - {in: query, name: loan_type, required: true, schema: {type: string}}
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
	responses:
	  400:
	    description: loan_type missing, not a loan type, or inactive (without include_inactive).
	  404:
	    description: The loan type does not exist.
	"""
	try:
		args = request_args()
		loan_type = args.get("loan_type") or loan_type
		if not loan_type:
			raise frappe.ValidationError("loan_type is required.")
		result = service.get_sub_types(loan_type, args.get("include_inactive", include_inactive))
		return send_response_list("success", "Sub-types retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Sub-types Error")


@frappe.whitelist(methods=["GET"])
def get_purposes(sub_type=None, loan_type=None, applicant_type=None, search=None, include_inactive=0):
	"""
	Purposes
	---
	tags:
	  - LOS Loan Type Tree
	summary: Level 3 nodes with their full path, under a sub-type, a whole loan type, or an applicant type.
	description: Use search for a single searchable purpose picker, e.g. "wedd" finds "Personal Loan > Wedding > Daughter Wedding".
	parameters:
	  - {in: query, name: sub_type, schema: {type: string}}
	  - {in: query, name: loan_type, schema: {type: string}}
	  - {in: query, name: applicant_type, schema: {type: string, enum: [Individual, Business]}}
	  - {in: query, name: search, schema: {type: string}}
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
	responses:
	  400:
	    description: sub_type or loan_type is the wrong level, or inactive (without include_inactive).
	  404:
	    description: The sub-type or loan type does not exist.
	"""
	try:
		args = request_args()
		result = service.get_purposes(
			args.get("sub_type") or sub_type,
			args.get("loan_type") or loan_type,
			args.get("applicant_type") or applicant_type,
			args.get("search") or search,
			args.get("include_inactive", include_inactive),
		)
		return send_response_list("success", "Purposes retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Purposes Error")


# ---------------------------------------------------------------- Whole setup (Loan Type Setup screen)


@frappe.whitelist(methods=["GET"])
def get_loan_type_setup(include_inactive=0):
	"""
	Loan Type Setup
	---
	tags:
	  - LOS Loan Type Tree
	summary: The whole setup for both applicant types in one call, in the Loan Type Setup screen's shape.
	description: >
	  Returns {setup, version}. setup is
	  {"Individual": [{id, name, subTypes: [{id, name, purposes: [{id, name}]}]}], "Business": [...]};
	  with include_inactive=1 each item also has isActive. version is optional to send back with the save.
	parameters:
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
	"""
	try:
		args = request_args()
		result = service.get_setup_page(args.get("include_inactive", include_inactive))
		return send_response("success", "Loan type setup retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Loan Type Setup Error")


@frappe.whitelist(methods=["PUT"])
def save_loan_type_setup():
	"""
	Save Loan Type Setup
	---
	tags:
	  - LOS Loan Type Tree
	summary: Saves loan types, sub-types and purposes for one or both applicant types in one call.
	description: >
	  Send the same shape the GET returns. For each applicant type sent: items with a known id are kept
	  (renamed if the name changed), items with an unknown or no id are created, and stored items left out
	  are deleted, or deactivated if something still uses them. Applicant types not sent are untouched.
	  If any part is invalid, nothing is saved. The response has the saved setup (with real IDs), the new version
	  and a summary. version is optional: if sent and the tree changed since, the save is refused with 409.
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        properties:
	          Individual:
	            type: array
	            items:
	              type: object
	              properties:
	                id: {type: string, description: 'Stored ID, or a temporary one for new items'}
	                name: {type: string}
	                subTypes:
	                  type: array
	                  items:
	                    type: object
	                    properties:
	                      id: {type: string}
	                      name: {type: string}
	                      purposes:
	                        type: array
	                        items:
	                          type: object
	                          properties:
	                            id: {type: string}
	                            name: {type: string}
	          Business:
	            type: array
	            description: Same shape as Individual.
	          version:
	            type: string
	            description: Optional. From get_loan_type_setup; protects against overwriting someone else's save.
	responses:
	  409:
	    description: A version was sent and someone else saved the setup since. Reload and save again.
	"""
	try:
		args = request_args()
		config = {key: args[key] for key in ("Individual", "Business") if key in args}
		result = service.save_setup(config, args.get("version"))
		frappe.db.commit()
		return send_response("success", "Loan type setup saved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Save LOS Loan Type Setup Error")
