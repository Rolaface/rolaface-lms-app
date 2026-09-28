import frappe

from rolaface_lms_app.utils.api_response import handle_api_error, send_response, send_response_list

from ..common import build_pagination, parse_pagination, request_args, require_id
from . import service
from .constant import DEFAULT_SORT_BY, DEFAULT_SORT_ORDER


@frappe.whitelist(methods=["POST"])
def create_channel():
	"""
	Create LOS Channel
	---
	tags:
	  - LOS Channel
	summary: Create a channel an application can come from, e.g. Branch or USSD.
	requestBody:
	  required: true
	  content:
	    application/json:
	      schema:
	        type: object
	        required:
	          - channel_name
	        properties:
	          channel_name:
	            type: string
	          is_active:
	            type: integer
	            enum: [0, 1]
	responses:
	  201:
	    description: Channel created successfully.
	  409:
	    description: A channel with this name already exists.
	"""
	try:
		result = service.create_channel(request_args())
		frappe.db.commit()
		return send_response("success", "Channel created successfully.", result, 201, 201)
	except Exception as e:
		return handle_api_error(e, "Create LOS Channel API Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def update_channel(id=None):
	"""
	Update LOS Channel
	---
	tags:
	  - LOS Channel
	summary: Update a channel's name or active flag.
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
	          channel_name:
	            type: string
	          is_active:
	            type: integer
	            enum: [0, 1]
	"""
	try:
		channel_id = require_id(id, "Channel")
		result = service.update_channel(channel_id, request_args())
		frappe.db.commit()
		return send_response("success", "Channel updated successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Update LOS Channel API Error")


@frappe.whitelist(methods=["GET"])
def get_channel_by_id(id=None):
	"""
	Get LOS Channel By ID
	---
	tags:
	  - LOS Channel
	summary: Channel details, including how many product assignment rules use it.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.get_channel_by_id(require_id(id, "Channel"))
		return send_response("success", "Channel retrieved successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Get LOS Channel By ID Error")


@frappe.whitelist(methods=["GET"])
def get_channels(page=1, page_size=20):
	"""
	List LOS Channels
	---
	tags:
	  - LOS Channel
	summary: Paginated channels with filters.
	parameters:
	  - {in: query, name: page, schema: {type: integer, default: 1}}
	  - {in: query, name: page_size, schema: {type: integer, default: 20, maximum: 500}}
	  - {in: query, name: search, description: Matches ID or channel name, schema: {type: string}}
	  - {in: query, name: channel_name, description: Partial match, schema: {type: string}}
	  - {in: query, name: is_active, schema: {type: integer, enum: [0, 1]}}
	  - {in: query, name: ids, description: Comma separated or JSON array of IDs, schema: {type: string}}
	  - {in: query, name: from_date, description: Created on or after, schema: {type: string, format: date}}
	  - {in: query, name: to_date, description: Created on or before, schema: {type: string, format: date}}
	  - {in: query, name: sort_by, schema: {type: string, enum: [name, channel_name, is_active, creation, modified], default: channel_name}}
	  - {in: query, name: sort_order, schema: {type: string, enum: [asc, desc], default: asc}}
	"""
	try:
		args = request_args()
		page, page_size = parse_pagination(args.get("page") or page, args.get("page_size") or page_size)
		records, total_records, _ = service.get_channels(
			args=args,
			page=page,
			page_size=page_size,
			sort_by=args.get("sort_by") or DEFAULT_SORT_BY,
			sort_order=args.get("sort_order") or DEFAULT_SORT_ORDER,
		)
		return send_response_list(
			"success",
			"Channels retrieved successfully.",
			{"data": records, "pagination": build_pagination(page, page_size, total_records)},
		)
	except Exception as e:
		return handle_api_error(e, "Get All LOS Channels Error")


@frappe.whitelist(methods=["GET"])
def get_active_channels():
	"""
	Active LOS Channels
	---
	tags:
	  - LOS Channel
	summary: Every active channel, unpaginated, for dropdowns and the source picker.
	"""
	try:
		return send_response_list("success", "Active channels retrieved successfully.", service.get_active_channels())
	except Exception as e:
		return handle_api_error(e, "Get Active LOS Channels Error")


@frappe.whitelist(methods=["DELETE"])
def delete_channel(id=None):
	"""
	Delete LOS Channel
	---
	tags:
	  - LOS Channel
	summary: Delete a channel. Refused while any product assignment rule uses it; disable it instead.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		service.delete_channel(require_id(id, "Channel"))
		frappe.db.commit()
		return send_response("success", "Channel deleted successfully.")
	except Exception as e:
		return handle_api_error(e, "Delete LOS Channel Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def enable_channel(id=None):
	"""
	Enable LOS Channel
	---
	tags:
	  - LOS Channel
	summary: Sets is_active to 1.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.toggle_channel_status(require_id(id, "Channel"), is_active=1)
		frappe.db.commit()
		return send_response("success", "Channel enabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Enable LOS Channel API Error")


@frappe.whitelist(methods=["PUT", "PATCH"])
def disable_channel(id=None):
	"""
	Disable LOS Channel
	---
	tags:
	  - LOS Channel
	summary: Sets is_active to 0.
	parameters:
	  - in: query
	    name: id
	    required: true
	    schema:
	      type: string
	"""
	try:
		result = service.toggle_channel_status(require_id(id, "Channel"), is_active=0)
		frappe.db.commit()
		return send_response("success", "Channel disabled successfully.", result)
	except Exception as e:
		return handle_api_error(e, "Disable LOS Channel API Error")
