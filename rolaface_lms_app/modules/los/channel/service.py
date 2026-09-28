from typing import Any, Dict, List, Tuple

import frappe

from ..common import build_order_by, count_records, search_or_filters
from .constant import (
	ALLOWED_CHANNEL_FIELDS,
	ALLOWED_SORT_FIELDS,
	CHANNEL_DOCTYPE,
	RETURN_FIELDS_GET_ALL,
	RETURN_FIELDS_GET_BY_ID,
	SEARCH_FIELDS,
)
from .utils import build_channel_filters, count_rules_using_channel, validate_channel_payload


def _ensure_exists(channel_id: str):
	if not frappe.db.exists(CHANNEL_DOCTYPE, channel_id):
		raise frappe.DoesNotExistError(f"Channel '{channel_id}' does not exist.")


def create_channel(data: Dict[str, Any]) -> Dict[str, Any]:
	validate_channel_payload(data, is_update=False)

	channel_doc = frappe.new_doc(CHANNEL_DOCTYPE)
	for field in ALLOWED_CHANNEL_FIELDS:
		if data.get(field) is not None:
			channel_doc.set(field, data.get(field))

	channel_doc.insert(ignore_permissions=True)
	return get_channel_by_id(channel_doc.name)


def update_channel(channel_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	_ensure_exists(channel_id)
	validate_channel_payload(data, is_update=True, channel_id=channel_id)

	channel_doc = frappe.get_doc(CHANNEL_DOCTYPE, channel_id)
	has_changes = False
	for field in ALLOWED_CHANNEL_FIELDS:
		if data.get(field) is not None and channel_doc.get(field) != data.get(field):
			channel_doc.set(field, data.get(field))
			has_changes = True

	if has_changes:
		channel_doc.save(ignore_permissions=True)

	return get_channel_by_id(channel_id)


def get_channel_by_id(channel_id: str) -> Dict[str, Any]:
	channel = frappe.db.get_value(CHANNEL_DOCTYPE, channel_id, RETURN_FIELDS_GET_BY_ID, as_dict=True)
	if not channel:
		raise frappe.DoesNotExistError(f"Channel '{channel_id}' does not exist.")

	channel["rules_count"] = count_rules_using_channel(channel_id)
	return channel


def get_channels(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int, int]:
	filters = build_channel_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS)
	order_by = build_order_by(CHANNEL_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS)

	channels = frappe.get_all(
		CHANNEL_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)

	total_records = count_records(CHANNEL_DOCTYPE, filters, or_filters)
	total_pages = (total_records + page_size - 1) // page_size
	return channels, total_records, total_pages


def get_active_channels() -> List[Dict[str, Any]]:
	"""Every active channel, for dropdowns and the product assignment source picker."""
	return frappe.get_all(
		CHANNEL_DOCTYPE,
		filters={"is_active": 1},
		fields=["name", "channel_name"],
		order_by="channel_name asc",
		limit_page_length=0,
	)


def delete_channel(channel_id: str):
	_ensure_exists(channel_id)

	rules_count = count_rules_using_channel(channel_id)
	if rules_count:
		raise frappe.ValidationError(
			f"Cannot delete this channel because {rules_count} product assignment rule(s) use it. "
			"Disable it instead."
		)

	frappe.delete_doc(CHANNEL_DOCTYPE, channel_id, ignore_permissions=True)


def toggle_channel_status(channel_id: str, is_active: int) -> Dict[str, Any]:
	_ensure_exists(channel_id)

	channel_doc = frappe.get_doc(CHANNEL_DOCTYPE, channel_id)
	if channel_doc.is_active == is_active:
		action = "active" if is_active else "inactive"
		raise frappe.ValidationError(f"Channel '{channel_doc.channel_name}' is already {action}.")

	channel_doc.is_active = is_active
	channel_doc.save(ignore_permissions=True)

	return {"name": channel_doc.name, "channel_name": channel_doc.channel_name, "is_active": channel_doc.is_active}
