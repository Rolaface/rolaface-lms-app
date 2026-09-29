"""Helpers shared by the LOS setup modules (channel, loan type tree, product assignment)."""

import hashlib
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
	"""
	Filter for "this JSON array contains value". Arrays are stored by dump_json, so the value is matched
	exactly as json.dumps writes it (quotes included), with LIKE's wildcards escaped: a channel named
	"USSD_2" must not match "USSDX2". Callers that act on the result should still check membership in Python.
	"""
	encoded = json.dumps(str(value))
	escaped = encoded.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
	return [fieldname, "like", f"%{escaped}%"]


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


# ---------------------------------------------------------------- Updates and status
# Status has one way in: the enable_* / disable_* endpoints. Updates only edit fields.


def validate_update_fields(data: Dict[str, Any], allowed: set, action: str):
	"""Rejects is_active on an update, and an update that sends nothing it can change."""
	if "is_active" in data:
		raise frappe.ValidationError(f"is_active cannot be changed by an update. Use enable_{action} or disable_{action}.")
	if not any(field in data for field in allowed):
		raise frappe.ValidationError(f"Nothing to update. Send at least one of: {', '.join(sorted(allowed))}.")


def ensure_status_change(current, is_active: int, label: str):
	if cint(current) == is_active:
		raise frappe.ValidationError(f"{label} is already {'active' if is_active else 'inactive'}.")


# ---------------------------------------------------------------- Version check for whole-page saves
# A page load returns a version. A save may send it back (optional): if someone saved in between,
# the save is refused with 409 instead of silently overwriting their work. Without it, the save goes through.


def table_version(doctype: str, *extra) -> str:
	"""Changes whenever a row of the table is added, changed or removed."""
	count, last_modified = frappe.db.sql(f"select count(*), max(modified) from `tab{doctype}`")[0]
	return hashlib.sha1("|".join(map(str, (count, last_modified, *extra))).encode()).hexdigest()[:16]


def single_modified(doctype: str) -> Optional[str]:
	row = frappe.db.sql("select value from `tabSingles` where doctype=%s and field='modified'", doctype)
	return row[0][0] if row else None


def check_version(sent, current: str):
	if sent and str(sent) != current:
		raise frappe.TimestampMismatchError(
			"Someone else saved this page after you loaded it. Reload to see their changes, then save again."
		)
