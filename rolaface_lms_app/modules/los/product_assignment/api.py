import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER

# ---------------------------------------------------------------- Whole page


@frappe.whitelist(methods=["GET"])
def get_product_assignment():
	"""
	Product Assignment Page
	---
	tags:
	  - LOS Product Assignment
	summary: Settings, every rule in priority order with names filled in, shadowed-rule warnings and the version to save with.
	"""
	try:
		return send_response("success", "Product assignment retrieved successfully.", service.get_product_assignment())
	except Exception as e:
		return handle_api_error(e, "Get LOS Product Assignment Error")


@frappe.whitelist(methods=["PUT"])
def save_product_assignment():
	"""
	Save Product Assignment Page
	---
	tags:
	  - LOS Product Assignment
	summary: Saves settings and the full ordered rule list together, for the screen's single Save button.
	description: >
	  Only what changed is written. Rules with a name are updated if their fields or position changed, rules
	  without one are created (active), stored rules left out are deleted. The response has a summary
	  (settings_updated, created, updated, deleted, unchanged).
	  Priority follows list order, and each rule keeps its active/inactive status. If any rule is invalid, nothing is saved.
	  version is optional: if sent and the page changed since, the save is refused with 409.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"several_match": "First match", "no_match": "Default Product", "default_product": {"pmv0rb831q": "PL-001"}, "rules": [{"name": "PAR-00001", "rule_name": "Staff personal loans", "sources": ["Branch"], "loan_types": ["pmv0rb831q"], "product": "PL-002", "condition": {"join": "AND", "groups": [{"name": "Staff with good score", "join": "AND", "clauses": [{"variable": "customer_type", "operator": "=", "value": "Staff"}, {"variable": "credit_score", "operator": ">=", "value": "650"}]}]}}, {"rule_name": "Everything else from Branch", "sources": ["Branch"], "loan_types": ["pmv0rb831q"], "product": "PL-001", "condition": null}]}
	      schema:
	        type: object
	        properties:
	          version:
	            type: string
	            description: Optional. From get_product_assignment; protects against overwriting someone else's save.
	          several_match:
	            type: string
	            enum: [First match, Manual Review]
	          no_match:
	            type: string
	            enum: [Manual Review, Default Product]
	          default_product:
	            type: object
	            description: '{loan type ID: Loan Product}. A loan type left out goes to manual review.'
	          rules:
	            type: array
	            items:
	              type: object
	              properties:
	                name: {type: string, description: Existing rule ID. Leave out for a new rule.}
	                rule_name: {type: string}
	                sources: {type: array, items: {type: string}}
	                loan_types: {type: array, items: {type: string}}
	                condition: {type: object}
	                product: {type: string}
	responses:
	  409:
	    description: A version was sent and someone else saved the page since. Reload and save again.
	"""
	try:
		result = service.save_product_assignment(request_args())
		frappe.db.commit()
		return send_response("success", "Product assignment saved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Save LOS Product Assignment Error")


# ---------------------------------------------------------------- Settings


@frappe.whitelist(methods=["GET"])
def get_settings():
	"""
	Product Assignment Settings
	---
	tags:
	  - LOS Product Assignment
	summary: Match mode, fallback and default product per loan type (as a map and as a list with names).
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
	            description: Replaces the whole map. At least one entry when no_match is Default Product.
	"""
	try:
		result = service.update_settings(request_args())
		frappe.db.commit()
		return send_response("success", "Settings updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Product Assignment Settings Error")


# ---------------------------------------------------------------- Rules


@frappe.whitelist(methods=["POST"])
def create_rule():
	"""
	Create Product Assignment Rule
	---
	tags:
	  - LOS Product Assignment
	summary: Add one rule. Without a priority it goes to the bottom. Active unless is_active is 0.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"rule_name": "Staff personal loans", "sources": ["Branch"], "loan_types": ["pmv0rb831q"], "product": "PL-002", "condition": {"join": "AND", "groups": [{"name": "Staff with good score", "join": "AND", "clauses": [{"variable": "customer_type", "operator": "=", "value": "Staff"}, {"variable": "credit_score", "operator": ">=", "value": "650"}]}]}}
	      schema:
	        type: object
	        required: [sources, loan_types, product]
	        properties:
	          rule_name: {type: string}
	          priority: {type: integer}
	          sources: {type: array, items: {type: string}, description: Channel IDs}
	          loan_types: {type: array, items: {type: string}, description: Level 1 loan type IDs}
	          condition:
	            type: object
	            description: '{join, groups: [{name, join, clauses: [{variable, operator, value}]}]}. Leave out to always match.'
	          product: {type: string, description: Loan Product}
	          is_active: {type: integer, enum: [0, 1], default: 1}
	responses:
	  201:
	    description: Rule created successfully.
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
	summary: Change any rule field. Fields left out keep their value. Use enable_rule / disable_rule for status.
	description: >
	  The rule is checked as a whole after the change. Channels, loan types and the product it already has may
	  stay even if they were disabled since; anything newly added must be active.
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
	      example: {"product": "PL-001"}
	      schema:
	        type: object
	        properties:
	          rule_name: {type: string}
	          priority: {type: integer}
	          sources: {type: array, items: {type: string}}
	          loan_types: {type: array, items: {type: string}}
	          condition: {type: object}
	          product: {type: string}
	responses:
	  400:
	    description: Nothing to update, is_active sent, or the rule is invalid after the change.
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
	summary: One rule with product, channel and loan type names.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
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
	summary: Paginated rules with filters.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: 'Matches ID, rule name or product', schema: {type: string}}
	  - {in: query, name: rule_name, description: Partial match, schema: {type: string}}
	  - {in: query, name: product, schema: {type: string}}
	  - {in: query, name: source, description: Rules that include this channel, schema: {type: string}}
	  - {in: query, name: loan_type, description: Rules that include this loan type, schema: {type: string}}
	  - {in: query, name: is_active, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: has_condition, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: priority_from, schema: {type: integer}}
	  - {in: query, name: priority_to, schema: {type: integer}}
	  - {in: query, name: ids, description: Comma separated or JSON array of IDs, schema: {type: string}}
	  - {in: query, name: from_date, schema: {type: string, format: date}}
	  - {in: query, name: to_date, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [name, rule_name, priority, product, is_active, creation, modified], default: priority}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: asc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records, _ = service.get_rules(
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
	summary: Delete one rule. Other rules keep their priority.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
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
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
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
	summary: Sets is_active to 0. The rule keeps its place in the order but is skipped when a product is picked.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
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


# ---------------------------------------------------------------- Matching


@frappe.whitelist(methods=["POST"])
def resolve_product():
	"""
	Resolve Product
	---
	tags:
	  - LOS Product Assignment
	summary: Pick the product for an application, or test the rules from the screen.
	description: >
	  Returns status (Rule matched, Loan type default or Manual review), the product and rule,
	  and every rule that matched. Inactive rules are skipped.
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
	          facts:
	            type: object
	            description: Values for the rule conditions.
	            example: {"customer_type": "Staff", "credit_score": 720}
	responses:
	  400:
	    description: A missing field, an unknown fact, a wrong level, or an inactive channel, loan type or purpose.
	  404:
	    description: The channel, loan type or purpose does not exist.
	"""
	try:
		result = service.resolve_product(request_args())
		return send_response("success", "Product resolved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Resolve LOS Product Error")


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
