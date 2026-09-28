"""Helpers shared by the LOS setup modules (channel, loan type tree, product assignment)."""

import json
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe.utils import cint

from rolaface_lms_app.utils.api_request import parse_api_payload

MAX_PAGE_SIZE = 500
SORT_ORDERS = ("asc", "desc")


def request_args() -> frappe._dict:
	"""
	Query string, form data and JSON body of the current request.

	Don't rely on frappe.local.form_dict or whitelisted function arguments here: the Bearer
	auth hook (auth_api validate_bearer_sid) calls frappe.set_user, which empties form_dict
	after Frappe has filled it, so query parameters would be lost.
	"""
	args = {}
	request = getattr(frappe.local, "request", None)
	if request is not None:
		args.update(request.args or {})
		args.update(request.form or {})
	args.update(parse_api_payload())
	args.pop("cmd", None)
	return frappe._dict(args)


def require_id(record_id: Optional[str], label: str) -> str:
	record_id = record_id or request_args().get("id")
	if not record_id:
		raise frappe.ValidationError(f"{label} ID is required as a query parameter (?id=...).")
	return str(record_id).strip()


def parse_pagination(page, page_size) -> Tuple[int, int]:
	try:
		page, page_size = int(page), int(page_size)
	except (TypeError, ValueError):
		raise frappe.ValidationError("page and page_size must be whole numbers.")
	if page < 1 or page_size < 1:
		raise frappe.ValidationError("page and page_size must be 1 or more.")
	return page, min(page_size, MAX_PAGE_SIZE)


def build_pagination(page: int, page_size: int, total: int) -> Dict[str, Any]:
	total_pages = (total + page_size - 1) // page_size
	return {
		"page": page,
		"page_size": page_size,
		"total": total,
		"total_pages": total_pages,
		"has_next": page < total_pages,
		"has_prev": page > 1,
	}


def build_order_by(doctype: str, sort_by: str, sort_order: str, allowed: set, tie_breaker: str = "name") -> str:
	if sort_by not in allowed:
		raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")
	sort_order = str(sort_order).lower()
	if sort_order not in SORT_ORDERS:
		raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")
	order_by = f"`tab{doctype}`.`{sort_by}` {sort_order}"
	if tie_breaker and tie_breaker != sort_by:
		order_by += f", `tab{doctype}`.`{tie_breaker}` asc"
	return order_by


def count_records(doctype: str, filters=None, or_filters=None) -> int:
	if not or_filters:
		return frappe.db.count(doctype, filters=filters or {})
	result = frappe.get_all(
		doctype, filters=filters or {}, or_filters=or_filters, fields=[{"COUNT": "name"}], as_list=True
	)
	return result[0][0] if result and result[0] else 0


def search_or_filters(search: Optional[str], fields: List[str]) -> List[list]:
	if not search or not str(search).strip():
		return []
	term = f"%{str(search).strip()}%"
	return [[field, "like", term] for field in fields]


def add_date_range(filters: Dict[str, Any], args: Dict[str, Any], field: str = "creation"):
	from_date, to_date = args.get("from_date"), args.get("to_date")
	if from_date and to_date:
		filters[field] = ["between", [from_date, to_date]]
	elif from_date:
		filters[field] = [">=", from_date]
	elif to_date:
		filters[field] = ["<=", to_date]


def parse_flag(value, label: str) -> int:
	if isinstance(value, bool):
		return int(value)
	if str(value).strip().lower() in ("1", "true", "yes"):
		return 1
	if str(value).strip().lower() in ("0", "false", "no"):
		return 0
	raise frappe.ValidationError(f"{label} must be 0 or 1.")


def parse_id_list(value) -> List[str]:
	"""Accepts a JSON array, a Python list or a comma separated string."""
	if value is None or value == "":
		return []
	if isinstance(value, str):
		value = value.strip()
		if value.startswith("["):
			value = load_json(value, [])
		else:
			value = value.split(",")
	if not isinstance(value, (list, tuple)):
		raise frappe.ValidationError("Expected a list of IDs.")
	seen, result = set(), []
	for item in value:
		item = str(item).strip()
		if item and item not in seen:
			seen.add(item)
			result.append(item)
	return result


def load_json(value, default=None):
	if value is None or value == "":
		return default
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except (TypeError, ValueError):
		raise frappe.ValidationError("Invalid JSON value.")


def dump_json(value) -> Optional[str]:
	# Frappe rejects lists in JSON fields, so always store a string.
	if value is None:
		return None
	return json.dumps(value, separators=(",", ":"))


def json_contains(fieldname: str, value: str) -> list:
	# JSON arrays are stored as ["a","b"], so a quoted match finds one member.
	return [fieldname, "like", f'%"{value}"%']


def name_map(doctype: str, names, label_field: str) -> Dict[str, Any]:
	names = [n for n in set(names or []) if n]
	if not names:
		return {}
	rows = frappe.get_all(doctype, filters={"name": ["in", names]}, fields=["name", label_field], limit_page_length=0)
	return {row.name: row.get(label_field) for row in rows}


def as_bool_flag(args: Dict[str, Any], key: str) -> Optional[int]:
	value = args.get(key)
	if value is None or value == "":
		return None
	return parse_flag(value, key)


def int_arg(args: Dict[str, Any], key: str) -> Optional[int]:
	value = args.get(key)
	if value is None or value == "":
		return None
	try:
		return int(value)
	except (TypeError, ValueError):
		raise frappe.ValidationError(f"{key} must be a whole number.")


def cint_or_none(value) -> Optional[int]:
	return None if value is None or value == "" else cint(value)
