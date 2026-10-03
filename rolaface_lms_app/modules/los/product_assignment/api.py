import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER


@frappe.whitelist(methods=["POST"])
def create_rule():
	"""
	Create Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: The rule for one loan product. A product can have only one rule; its ID is the product's ID.
	description: >
	  An application is assigned this product when it comes from one of the sources, is for one of the loan types
	  and meets the condition (no condition means always). Active unless is_active is 0.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"product": "PL-002", "sources": ["Branch"], "loan_types": ["pmv0rb831q"], "condition": {"join": "AND", "groups": [{"name": "Staff with good score", "join": "AND", "clauses": [{"variable": "customer_type", "operator": "=", "value": "Staff"}, {"variable": "credit_score", "operator": ">=", "value": "650"}]}]}}
	      schema:
	        type: object
	        required: [product, sources, loan_types]
	        properties:
	          product: {type: string, description: An enabled Loan Product without a rule yet}
	          sources: {type: array, items: {type: string}, description: Channel IDs}
	          loan_types: {type: array, items: {type: string}, description: Level 1 loan type IDs}
	          condition:
	            type: object
	            description: '{join, groups: [{name, join, clauses: [{variable, operator, value}]}]}. Leave out to always match.'
	          is_active: {type: integer, enum: [0, 1], default: 1}
	responses:
	  201:
	    description: Rule created successfully.
	  409:
	    description: The loan product already has a rule. Update it instead.
	"""
	try:
		result = service.create_rule(request_args())
		frappe.db.commit()
		return send_response("success", "Product assignment rule created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Product Assignment Rule API Error")


@frappe.whitelist(methods=["PUT"])
def update_rule(id=None):
	"""
	Update Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: Change the sources, loan types or condition. Fields left out keep their value. Use enable_rule / disable_rule for status.
	description: >
	  The product cannot change. Channels and loan types the rule already has may stay even if they were disabled
	  since; anything newly added must be active.
	parameters:
	  - {in: query, name: id, required: true, description: Loan Product ID, schema: {type: string}}
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"sources": ["Branch"], "loan_types": ["pmv0rb831q"], "condition": null}
	      schema:
	        type: object
	        properties:
	          sources: {type: array, items: {type: string}}
	          loan_types: {type: array, items: {type: string}}
	          condition: {type: object, description: Send null to remove the condition.}
	responses:
	  400:
	    description: Nothing to update, is_active or a different product sent, or the rule is invalid after the change.
	"""
	try:
		result = service.update_rule(require_id(id, "Rule"), request_args())
		frappe.db.commit()
		return send_response("success", "Product assignment rule updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Product Assignment Rule API Error")


@frappe.whitelist(methods=["GET"])
def get_rule_by_id(id=None):
	"""
	Get Product Assignment Rule By ID
	---
	tags:
	  - LOS Product Assignment
	summary: One product's rule with channel and loan type names.
	parameters:
	  - {in: query, name: id, required: true, description: Loan Product ID, schema: {type: string}}
	"""
	try:
		result = service.get_rule_by_id(require_id(id, "Rule"))
		return send_response("success", "Product assignment rule retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Product Assignment Rule By ID Error")


@frappe.whitelist(methods=["GET"])
def get_rules(page=1, page_size=20):
	"""
	List Product Assignment Rules
	---
	tags:
	  - LOS Product Assignment
	summary: Paginated rules with filters, one per loan product.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches loan product ID or name, schema: {type: string}}
	  - {in: query, name: product, schema: {type: string}}
	  - {in: query, name: source, description: Rules that include this channel, schema: {type: string}}
	  - {in: query, name: loan_type, description: Rules that include this loan type, schema: {type: string}}
	  - {in: query, name: is_active, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: has_condition, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: ids, description: Comma separated or JSON array of loan product IDs, schema: {type: string}}
	  - {in: query, name: from_date, schema: {type: string, format: date}}
	  - {in: query, name: to_date, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [product_name, name, is_active, creation, modified], default: product_name}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: asc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records = service.get_rules(
			args=args,
			page=page,
			page_size=page_size,
			sort_by=args.get("sort_by") or DEFAULT_SORT_BY,
			sort_order=args.get("sort_order") or DEFAULT_SORT_ORDER,
		)
		return send_response_list(
			"success",
			"Product assignment rules retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get All LOS Product Assignment Rules Error")


@frappe.whitelist(methods=["DELETE"])
def delete_rule(id=None):
	"""
	Delete Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: Delete a loan product's rule.
	parameters:
	  - {in: query, name: id, required: true, description: Loan Product ID, schema: {type: string}}
	"""
	try:
		service.delete_rule(require_id(id, "Rule"))
		frappe.db.commit()
		return send_response("success", "Product assignment rule deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Product Assignment Rule Error")


@frappe.whitelist(methods=["PUT"])
def enable_rule(id=None):
	"""
	Enable Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: Sets is_active to 1. The rule is used again when a product is picked.
	parameters:
	  - {in: query, name: id, required: true, description: Loan Product ID, schema: {type: string}}
	responses:
	  400:
	    description: The rule is already active.
	"""
	try:
		result = service.toggle_rule_status(require_id(id, "Rule"), is_active=1)
		frappe.db.commit()
		return send_response("success", "Product assignment rule enabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Enable LOS Product Assignment Rule API Error")


@frappe.whitelist(methods=["PUT"])
def disable_rule(id=None):
	"""
	Disable Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: Sets is_active to 0. The rule is skipped when a product is picked.
	parameters:
	  - {in: query, name: id, required: true, description: Loan Product ID, schema: {type: string}}
	responses:
	  400:
	    description: The rule is already inactive.
	"""
	try:
		result = service.toggle_rule_status(require_id(id, "Rule"), is_active=0)
		frappe.db.commit()
		return send_response("success", "Product assignment rule disabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Disable LOS Product Assignment Rule API Error")


@frappe.whitelist(methods=["GET"])
def get_settings():
	"""
	Product Assignment Settings
	---
	tags:
	  - LOS Product Assignment
	summary: What happens when several rules or no rule match, and the default product per loan type (as a map and as a list with names).
	"""
	try:
		return send_response("success", "Settings retrieved successfully.", service.get_settings())
	except Exception as e:
		return handle_api_error(e, "Get LOS Product Assignment Settings Error")


@frappe.whitelist(methods=["PUT"])
def update_settings():
	"""
	Update Product Assignment Settings
	---
	tags:
	  - LOS Product Assignment
	summary: Update any of several_match, no_match, default_product. Fields left out keep their value.
	requestBody:
	  content:
	    application/json:
	      example: {"several_match": "First match", "no_match": "Default Product", "default_product": {"pmv0rb831q": "PL-001"}}
	      schema:
	        type: object
	        properties:
	          several_match:
	            type: string
	            enum: [First match, Manual Review]
	          no_match:
	            type: string
	            enum: [Manual Review, Default Product]
	          default_product:
	            type: object
	            description: '{loan type ID: Loan Product}. Replaces the whole map. At least one entry when no_match is Default Product.'
	"""
	try:
		result = service.update_settings(request_args())
		frappe.db.commit()
		return send_response("success", "Settings updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Product Assignment Settings Error")


@frappe.whitelist(methods=["POST"])
def test_rules():
	"""
	Test Product Assignment Rules
	---
	tags:
	  - LOS Product Assignment
	summary: Check which product an application would get, to confirm the rules are set up correctly.
	description: >
	  status is Rule matched, Loan type default, Manual review, or Conflict when more than one product's rule
	  matches (the rules overlap and should be fixed). matched_rules lists every product whose rule matched.
	  Inactive rules and disabled products are skipped.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"source": "Branch", "loan_type": "pmv0rb831q", "facts": {"customer_type": "Staff", "credit_score": 720}}
	      schema:
	        type: object
	        required: [source]
	        properties:
	          source: {type: string, description: Channel ID}
	          loan_type: {type: string, description: Level 1 loan type ID. Or send purpose instead.}
	          purpose: {type: string, description: Level 3 purpose ID. Its loan type is used.}
	          facts: {type: object, description: Values for the rule conditions.}
	responses:
	  400:
	    description: A missing field, an unknown fact, a wrong level, or an inactive channel, loan type or purpose.
	  404:
	    description: The channel, loan type or purpose does not exist.
	"""
	try:
		result = service.test_rules(request_args())
		return send_response("success", "Product assignment rules tested successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Test LOS Product Assignment Rules Error")


@frappe.whitelist(methods=["GET"])
def get_condition_variables():
	"""
	Condition Variables
	---
	tags:
	  - LOS Product Assignment
	summary: Variables a rule condition can use, with allowed operators and options, for the condition builder.
	"""
	try:
		return send_response_list("success", "Condition variables retrieved successfully.", service.get_condition_variables())
	except Exception as e:
		return handle_api_error(e, "Get LOS Condition Variables Error")
