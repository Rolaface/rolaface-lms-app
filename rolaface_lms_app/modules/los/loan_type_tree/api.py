import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER

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


@frappe.whitelist(methods=["PUT", "PATCH"])
def update_node(id=None):
	"""
	Update Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Rename a node or change its active flag. Parent and applicant type cannot change.
	description: Deactivating a node also deactivates everything under it.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	requestBody:
	  content:
	    application/json:
	      schema:
	        type: object
	        properties:
	          node_name:
	            type: string
	          is_active:
	            type: integer
	            enum: [0, 1]
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


@frappe.whitelist(methods=["GET"])
def get_nodes(page=1, page_size=20):
	"""
	List Loan Type Tree Nodes
	---
	tags:
	  - LOS Loan Type Tree
	summary: Paginated flat list of nodes with filters.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches ID or name, schema: {type: string}}
	  - {in: query, name: node_name, description: Partial match, schema: {type: string}}
	  - {in: query, name: applicant_type, schema: {type: string, enum: [Individual, Business]}}
	  - {in: query, name: level, description: 1 loan type, 2 sub-type, 3 purpose, schema: {type: integer, enum: [1, 2, 3]}}
	  - {in: query, name: parent_node, description: Direct children of this node, schema: {type: string}}
	  - {in: query, name: is_root, description: 1 for nodes without a parent, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: loan_type, description: Everything under this loan type, schema: {type: string}}
	  - {in: query, name: sub_type, description: Everything under this sub-type, schema: {type: string}}
	  - {in: query, name: is_active, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: is_group, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: ids, description: Comma separated or JSON array of IDs, schema: {type: string}}
	  - {in: query, name: from_date, schema: {type: string, format: date}}
	  - {in: query, name: to_date, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [name, node_name, applicant_type, level, is_active, creation, modified], default: level}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: asc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records, _ = service.get_nodes(
			args=args,
			page=page,
			page_size=page_size,
			sort_by=args.get("sort_by") or DEFAULT_SORT_BY,
			sort_order=args.get("sort_order") or DEFAULT_SORT_ORDER,
		)
		return send_response_list(
			"success",
			"Loan type tree nodes retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get All LOS Loan Type Tree Nodes Error")


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
	"""
	try:
		service.delete_node(require_id(id, "Node"))
		frappe.db.commit()
		return send_response("success", "Loan type tree node deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Loan Type Tree Node Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
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
	"""
	try:
		result = service.toggle_node_status(require_id(id, "Node"), is_active=1)
		frappe.db.commit()
		return send_response("success", "Loan type tree node enabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Enable LOS Loan Type Tree Node API Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def disable_node(id=None):
	"""
	Disable Loan Type Tree Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Sets is_active to 0 on the node and everything under it.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.toggle_node_status(require_id(id, "Node"), is_active=0)
		frappe.db.commit()
		return send_response("success", "Loan type tree node disabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Disable LOS Loan Type Tree Node API Error")


# ---------------------------------------------------------------- Lookups


@frappe.whitelist(methods=["GET"])
def get_tree(applicant_type=None, loan_type=None, include_inactive=0):
	"""
	Loan Type Tree
	---
	tags:
	  - LOS Loan Type Tree
	summary: Nested loan type > sub-type > purpose tree for the Loan Type Setup screen and the application wizard.
	parameters:
	  - {in: query, name: applicant_type, schema: {type: string, enum: [Individual, Business]}}
	  - {in: query, name: loan_type, description: Only this loan type's branch, schema: {type: string}}
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
	"""
	try:
		args = request_args()
		result = service.get_tree(
			args.get("applicant_type") or applicant_type,
			args.get("loan_type") or loan_type,
			args.get("include_inactive", include_inactive),
		)
		return send_response_list("success", "Loan type tree retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Loan Type Tree Error")


@frappe.whitelist(methods=["GET"])
def get_loan_types(applicant_type=None, include_inactive=0):
	"""
	Loan Types
	---
	tags:
	  - LOS Loan Type Tree
	summary: Level 1 nodes, optionally for one applicant type.
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
	summary: Level 2 nodes under one loan type.
	parameters:
	  - {in: query, name: loan_type, required: true, schema: {type: string}}
	  - {in: query, name: include_inactive, schema: {type: integer, enum: [0, 1], default: 0}}
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


@frappe.whitelist(methods=["GET"])
def get_node_path(id=None):
	"""
	Loan Type Path of a Node
	---
	tags:
	  - LOS Loan Type Tree
	summary: Applicant type, loan type, sub-type and purpose for any node, e.g. the loan type of a purpose.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.get_node_path(require_id(id, "Node"))
		return send_response("success", "Node path retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Node Path Error")
