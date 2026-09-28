from typing import Any, Dict, List, Optional, Tuple

import frappe

from ..common import build_order_by, count_records, name_map, search_or_filters
from .constant import (
	ALLOWED_SORT_FIELDS,
	LEVEL_LOAN_TYPE,
	LEVEL_PURPOSE,
	LEVEL_SUB_TYPE,
	PARENT_FIELD,
	RETURN_FIELDS_GET_ALL,
	RETURN_FIELDS_GET_BY_ID,
	RETURN_FIELDS_LOOKUP,
	SEARCH_FIELDS,
	TREE_DOCTYPE,
)
from .utils import (
	build_node_filters,
	clean_node_name,
	count_node_usage,
	descendant_filters,
	ensure_unique_name,
	require_node,
	resolve_hierarchy,
	validate_applicant_type,
	validate_update_payload,
)


def _add_names(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	"""Adds parent, loan type and sub-type names with one extra query for the whole page."""
	ids = set()
	for row in rows:
		ids.update(filter(None, (row.get("parent_node"), row.get("loan_type"), row.get("sub_type"))))
	names = name_map(TREE_DOCTYPE, ids, "node_name")
	for row in rows:
		row["parent_node_name"] = names.get(row.get("parent_node"))
		row["loan_type_name"] = names.get(row.get("loan_type"))
		row["sub_type_name"] = names.get(row.get("sub_type"))
	return rows


def _active_filter(filters: Dict[str, Any], include_inactive) -> Dict[str, Any]:
	if not frappe.utils.cint(include_inactive):
		filters["is_active"] = 1
	return filters


# ---------------------------------------------------------------- CRUD


def create_node(data: Dict[str, Any]) -> Dict[str, Any]:
	node_name = clean_node_name(data.get("node_name"))
	hierarchy = resolve_hierarchy(data)
	ensure_unique_name(node_name, hierarchy["applicant_type"], hierarchy["parent"])

	node_doc = frappe.new_doc(TREE_DOCTYPE)
	node_doc.update(
		{
			"node_name": node_name,
			"applicant_type": hierarchy["applicant_type"],
			"level": hierarchy["level"],
			PARENT_FIELD: hierarchy["parent"],
			"loan_type": hierarchy["loan_type"],
			"sub_type": hierarchy["sub_type"],
			"is_group": 1 if hierarchy["level"] < LEVEL_PURPOSE else 0,
			"is_active": 1 if data.get("is_active") is None else frappe.utils.cint(data.get("is_active")),
		}
	)
	node_doc.insert(ignore_permissions=True)
	return get_node_by_id(node_doc.name)


def update_node(node_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	node = require_node(node_id)
	validate_update_payload(node, data)

	node_doc = frappe.get_doc(TREE_DOCTYPE, node_id)
	has_changes = False

	if data.get("node_name") and data["node_name"] != node_doc.node_name:
		node_doc.node_name = data["node_name"]
		has_changes = True

	is_active = data.get("is_active")
	if is_active is not None and is_active != node_doc.is_active:
		if is_active:
			_ensure_parent_active(node)
		node_doc.is_active = is_active
		has_changes = True

	if has_changes:
		node_doc.save(ignore_permissions=True)
		if is_active == 0:
			_deactivate_descendants(node)

	return get_node_by_id(node_id)


def _ensure_parent_active(node: Dict[str, Any]):
	parent_id = node.get(PARENT_FIELD)
	if parent_id and not frappe.db.get_value(TREE_DOCTYPE, parent_id, "is_active"):
		raise frappe.ValidationError("Enable the parent first, then this one.")


def _deactivate_descendants(node: Dict[str, Any]) -> int:
	filters = descendant_filters(node)
	if not filters:
		return 0
	filters["is_active"] = 1
	descendants = frappe.get_all(TREE_DOCTYPE, filters=filters, pluck="name", limit_page_length=0)
	if descendants:
		frappe.db.set_value(TREE_DOCTYPE, {"name": ["in", descendants]}, "is_active", 0)
	return len(descendants)


def get_node_by_id(node_id: str) -> Dict[str, Any]:
	node = frappe.db.get_value(TREE_DOCTYPE, node_id, RETURN_FIELDS_GET_BY_ID, as_dict=True)
	if not node:
		raise frappe.DoesNotExistError(f"Loan type tree node '{node_id}' does not exist.")

	_add_names([node])
	node["children_count"] = frappe.db.count(TREE_DOCTYPE, {PARENT_FIELD: node_id})
	if node.level == LEVEL_LOAN_TYPE:
		node["usage"] = count_node_usage(node_id)
	return node


def get_nodes(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int, int]:
	filters = build_node_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS)
	order_by = build_order_by(TREE_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS, tie_breaker="node_name")

	nodes = frappe.get_all(
		TREE_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)

	total_records = count_records(TREE_DOCTYPE, filters, or_filters)
	total_pages = (total_records + page_size - 1) // page_size
	return _add_names(nodes), total_records, total_pages


def delete_node(node_id: str):
	node = require_node(node_id)

	children = frappe.db.count(TREE_DOCTYPE, {PARENT_FIELD: node_id})
	if children:
		raise frappe.ValidationError(
			f"Cannot delete '{node.node_name}' because it has {children} item(s) under it. Disable it instead."
		)

	if node.level == LEVEL_LOAN_TYPE:
		usage = count_node_usage(node_id)
		if usage["rules"] or usage["default_product"]:
			raise frappe.ValidationError(
				f"Cannot delete '{node.node_name}' because product assignment uses it "
				f"({usage['rules']} rule(s), default product: {'yes' if usage['default_product'] else 'no'}). "
				"Disable it instead."
			)

	frappe.delete_doc(TREE_DOCTYPE, node_id, ignore_permissions=True)


def toggle_node_status(node_id: str, is_active: int) -> Dict[str, Any]:
	node = require_node(node_id)
	if node.is_active == is_active:
		raise frappe.ValidationError(f"'{node.node_name}' is already {'active' if is_active else 'inactive'}.")

	result = update_node(node_id, {"is_active": is_active})
	return {"name": result["name"], "node_name": result["node_name"], "is_active": result["is_active"]}


# ---------------------------------------------------------------- Lookups


def get_tree(applicant_type: Optional[str] = None, loan_type: Optional[str] = None, include_inactive=0) -> List[Dict]:
	"""The full loan type > sub-type > purpose tree in one query, nested in memory."""
	filters = _active_filter({}, include_inactive)
	if applicant_type:
		filters["applicant_type"] = validate_applicant_type(applicant_type)

	rows = frappe.get_all(
		TREE_DOCTYPE,
		filters=filters,
		or_filters=[["name", "=", loan_type], ["loan_type", "=", loan_type]] if loan_type else None,
		fields=RETURN_FIELDS_LOOKUP,
		order_by="level asc, node_name asc",
		limit_page_length=0,
	)

	by_id, roots = {}, []
	for row in rows:
		row["children"] = []
		if row.level == LEVEL_LOAN_TYPE:
			roots.append(row)
		elif row.parent_node in by_id:
			by_id[row.parent_node]["children"].append(row)
		else:
			continue  # parent is inactive or filtered out, so hide the branch
		by_id[row.name] = row
	return roots


def get_loan_types(applicant_type: Optional[str] = None, include_inactive=0) -> List[Dict[str, Any]]:
	filters = _active_filter({"level": LEVEL_LOAN_TYPE}, include_inactive)
	if applicant_type:
		filters["applicant_type"] = validate_applicant_type(applicant_type)
	return frappe.get_all(
		TREE_DOCTYPE, filters=filters, fields=RETURN_FIELDS_LOOKUP, order_by="node_name asc", limit_page_length=0
	)


def get_sub_types(loan_type: str, include_inactive=0) -> List[Dict[str, Any]]:
	require_node(loan_type, expected_level=LEVEL_LOAN_TYPE)
	filters = _active_filter({"level": LEVEL_SUB_TYPE, PARENT_FIELD: loan_type}, include_inactive)
	return frappe.get_all(
		TREE_DOCTYPE, filters=filters, fields=RETURN_FIELDS_LOOKUP, order_by="node_name asc", limit_page_length=0
	)


def get_purposes(
	sub_type: Optional[str] = None,
	loan_type: Optional[str] = None,
	applicant_type: Optional[str] = None,
	search: Optional[str] = None,
	include_inactive=0,
) -> List[Dict[str, Any]]:
	"""Purposes under a sub-type, under a whole loan type, or across an applicant type, with their path."""
	filters = _active_filter({"level": LEVEL_PURPOSE}, include_inactive)
	if sub_type:
		require_node(sub_type, expected_level=LEVEL_SUB_TYPE)
		filters["sub_type"] = sub_type
	if loan_type:
		require_node(loan_type, expected_level=LEVEL_LOAN_TYPE)
		filters["loan_type"] = loan_type
	if applicant_type:
		filters["applicant_type"] = validate_applicant_type(applicant_type)
	if search and str(search).strip():
		filters["node_name"] = ["like", f"%{str(search).strip()}%"]

	rows = frappe.get_all(
		TREE_DOCTYPE, filters=filters, fields=RETURN_FIELDS_LOOKUP, order_by="node_name asc", limit_page_length=0
	)
	_add_names(rows)
	for row in rows:
		row["path"] = " > ".join(filter(None, (row.loan_type_name, row.sub_type_name, row.node_name)))
	if not sub_type:
		rows.sort(key=lambda r: r["path"].lower())
	return rows


def get_node_path(node_id: str) -> Dict[str, Any]:
	"""Applicant type, loan type, sub-type and purpose for any node, e.g. the loan type of a purpose."""
	node = require_node(node_id)
	names = name_map(TREE_DOCTYPE, [node.loan_type, node.sub_type], "node_name")

	def ref(ref_id):
		return {"name": ref_id, "node_name": names.get(ref_id) or ""} if ref_id else None

	own = {"name": node.name, "node_name": node.node_name}
	return {
		"applicant_type": node.applicant_type,
		"level": node.level,
		"loan_type": own if node.level == LEVEL_LOAN_TYPE else ref(node.loan_type),
		"sub_type": own if node.level == LEVEL_SUB_TYPE else ref(node.sub_type),
		"purpose": own if node.level == LEVEL_PURPOSE else None,
		"is_active": node.is_active,
	}
