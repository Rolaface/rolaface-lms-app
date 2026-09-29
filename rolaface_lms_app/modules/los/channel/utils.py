from typing import Any, Dict, Optional

import frappe

from ..common import add_date_range, as_bool_flag, json_contains, parse_flag, parse_id_list, validate_update_fields
from .constant import ALLOWED_UPDATE_FIELDS, CHANNEL_DOCTYPE, CHANNEL_NAME_MAX_LENGTH, RULE_DOCTYPE


def validate_channel_payload(data: Dict[str, Any], is_update: bool = False, channel_id: Optional[str] = None):
	if is_update:
		validate_update_fields(data, ALLOWED_UPDATE_FIELDS, "channel")

	if "channel_name" in data or not is_update:
		channel_name = str(data.get("channel_name") or "").strip()
		if not channel_name:
			raise frappe.ValidationError("Channel Name is required.")
		if len(channel_name) > CHANNEL_NAME_MAX_LENGTH:
			raise frappe.ValidationError(f"Channel Name cannot be longer than {CHANNEL_NAME_MAX_LENGTH} characters.")

		duplicate_filters = {"channel_name": channel_name}
		if channel_id:
			duplicate_filters["name"] = ["!=", channel_id]
		if frappe.db.exists(CHANNEL_DOCTYPE, duplicate_filters):
			raise frappe.DuplicateEntryError(f"Channel '{channel_name}' already exists.")
		data["channel_name"] = channel_name

	if not is_update and data.get("is_active") is not None:
		data["is_active"] = parse_flag(data.get("is_active"), "is_active")


def build_channel_filters(args: Dict[str, Any]) -> Dict[str, Any]:
	filters = {}

	is_active = as_bool_flag(args, "is_active")
	if is_active is not None:
		filters["is_active"] = is_active

	if args.get("channel_name"):
		filters["channel_name"] = ["like", f"%{str(args.get('channel_name')).strip()}%"]

	ids = parse_id_list(args.get("ids"))
	if ids:
		filters["name"] = ["in", ids]

	add_date_range(filters, args)
	return filters


def count_rules_using_channel(channel_id: str) -> int:
	return frappe.db.count(RULE_DOCTYPE, filters=[json_contains("sources", channel_id)])
