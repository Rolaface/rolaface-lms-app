import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER


@frappe.whitelist(methods=["POST"])
def create_document_setup():
	"""
	Create LOS Document Setup
	---
	tags:
	  - LOS Document Setup
	summary: Set the documents applicants must provide for a loan product.
	description: >
	  One setup per loan product; its ID is the loan product's ID. Documents are kept in the order sent.
	  Names are trimmed and must be unique within the product (case does not matter).
	  is_required defaults to 1 when left out.
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"loan_product": "HL-PUR", "documents": [{"document_name": "NRC copy", "is_required": 1}, {"document_name": "Last 3 payslips", "is_required": 1}, {"document_name": "Proof of residence", "is_required": 0}]}
	      schema:
	        type: object
	        required:
	          - loan_product
	          - documents
	        properties:
	          loan_product:
	            type: string
	            description: An enabled Loan Product ID.
	          documents:
	            type: array
	            minItems: 1
	            maxItems: 100
	            items:
	              type: object
	              required:
	                - document_name
	              properties:
	                document_name:
	                  type: string
	                  maxLength: 140
	                is_required:
	                  type: integer
	                  enum: [0, 1]
	                  default: 1
	responses:
	  201:
	    description: Document setup created successfully.
	  400:
	    description: Missing, unknown or disabled loan product, or an invalid document list.
	  409:
	    description: Documents are already set up for this loan product. Use update_document_setup.
	"""
	try:
		result = service.create_document_setup(request_args())
		frappe.db.commit()
		return send_response("success", "Document setup created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Document Setup API Error")


@frappe.whitelist(methods=["PUT"])
def update_document_setup(id=None):
	"""
	Update LOS Document Setup
	---
	tags:
	  - LOS Document Setup
	summary: Replace a loan product's document list.
	description: >
	  The list sent replaces the stored one, in the order sent. The loan product cannot be changed;
	  delete the setup and create one for the other product instead.
	parameters:
	  - in: query
	    name: id
	    required: true
	    description: Loan Product ID
	    schema:
	      type: string
	requestBody:
	  required: true
	  content:
	    application/json:
	      example: {"documents": [{"document_name": "NRC copy", "is_required": 1}, {"document_name": "Bank statement (6 months)", "is_required": 1}]}
	      schema:
	        type: object
	        required:
	          - documents
	        properties:
	          documents:
	            type: array
	            minItems: 1
	            maxItems: 100
	            items:
	              type: object
	              required:
	                - document_name
	              properties:
	                document_name:
	                  type: string
	                  maxLength: 140
	                is_required:
	                  type: integer
	                  enum: [0, 1]
	                  default: 1
	responses:
	  400:
	    description: Nothing to update, an invalid document list, or a different loan_product was sent.
	  404:
	    description: No documents are set up for this loan product.
	"""
	try:
		setup_id = require_id(id, "Document Setup")
		result = service.update_document_setup(setup_id, request_args())
		frappe.db.commit()
		return send_response("success", "Document setup updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Document Setup API Error")


@frappe.whitelist(methods=["GET"])
def get_document_setup_by_id(id=None):
	"""
	Get LOS Document Setup By ID
	---
	tags:
	  - LOS Document Setup
	summary: A loan product's documents in display order, with document and required counts.
	parameters:
	  - in: query
	    name: id
	    required: true
	    description: Loan Product ID
	    schema:
	      type: string
	responses:
	  404:
	    description: No documents are set up for this loan product.
	"""
	try:
		result = service.get_document_setup_by_id(require_id(id, "Document Setup"))
		return send_response("success", "Document setup retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Document Setup By ID Error")


@frappe.whitelist(methods=["GET"])
def get_document_setups(page=1, page_size=20):
	"""
	List LOS Document Setups
	---
	tags:
	  - LOS Document Setup
	summary: Paginated loan products that have documents set up, with document and required counts.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches loan product ID or name, schema: {type: string}}
	  - {in: query, name: ids, description: Comma separated or JSON array of loan product IDs, schema: {type: string}}
	  - {in: query, name: from_date, description: Created on or after, schema: {type: string, format: date}}
	  - {in: query, name: to_date, description: Created on or before, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [name, loan_product, product_name, creation, modified], default: product_name}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: asc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records, _ = service.get_document_setups(
			args=args,
			page=page,
			page_size=page_size,
			sort_by=args.get("sort_by") or DEFAULT_SORT_BY,
			sort_order=args.get("sort_order") or DEFAULT_SORT_ORDER,
		)
		return send_response_list(
			"success",
			"Document setups retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get All LOS Document Setups Error")


@frappe.whitelist(methods=["GET"])
def get_products_without_documents():
	"""
	List Loan Products Without Documents
	---
	tags:
	  - LOS Document Setup
	summary: Enabled loan products that have no document setup yet. For the product dropdown when adding a setup.
	parameters:
	  - {in: query, name: search, description: Matches loan product ID or name, schema: {type: string}}
	"""
	try:
		result = service.get_products_without_documents(request_args())
		return send_response("success", "Loan products retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get Loan Products Without Documents Error")


@frappe.whitelist(methods=["DELETE"])
def delete_document_setup(id=None):
	"""
	Delete LOS Document Setup
	---
	tags:
	  - LOS Document Setup
	summary: Remove all documents set up for a loan product.
	parameters:
	  - in: query
	    name: id
	    required: true
	    description: Loan Product ID
	    schema:
	      type: string
	responses:
	  404:
	    description: No documents are set up for this loan product.
	"""
	try:
		service.delete_document_setup(require_id(id, "Document Setup"))
		frappe.db.commit()
		return send_response("success", "Document setup deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Document Setup Error")
