from typing import Any, Dict, List, Optional

import frappe

from ..common import check_version, ensure_status_change, name_map, parse_flag, table_version
from .constant import (
	APPLICANT_TYPES,
	LEVEL_LABELS,
	LEVEL_LOAN_TYPE,
	LEVEL_PURPOSE,
	LEVEL_SUB_TYPE,
	PARENT_FIELD,
	RETURN_FIELDS_GET_BY_ID,
	RETURN_FIELDS_LOOKUP,
	TREE_DOCTYPE,
)
from .utils import (
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


def _require_parent(node_id: str, level: int, include_inactive) -> Dict[str, Any]:
	node = require_node(node_id, expected_level=level)
	if not node.is_active and not frappe.utils.cint(include_inactive):
		raise frappe.ValidationError(f"{LEVEL_LABELS[level]} '{node.node_name}' is inactive.")
	return node


def _insert_node(node_name: str, applicant_type: Optional[str], parent_id: Optional[str], is_active: int = 1) -> str:
	node_name = clean_node_name(node_name)
	hierarchy = resolve_hierarchy({"applicant_type": applicant_type, "parent_node": parent_id})
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
			"is_active": 1 if is_active else 0,
		}
	)
	node_doc.insert(ignore_permissions=True)
	return node_doc.name


def _update_node_fields(node_id: str, node_name: Optional[str] = None, is_active: Optional[int] = None) -> int:
	node = require_node(node_id)
	node_doc = frappe.get_doc(TREE_DOCTYPE, node_id)
	has_changes = False

	if node_name is not None:
		node_name = clean_node_name(node_name)
		if node_name != node_doc.node_name:
			ensure_unique_name(node_name, node.applicant_type, node.get(PARENT_FIELD), node.name)
			node_doc.node_name = node_name
			has_changes = True

	if is_active is not None and is_active != node_doc.is_active:
		if is_active:
			_ensure_parent_active(node)
		node_doc.is_active = is_active
		has_changes = True

	if not has_changes:
		return 0
	node_doc.save(ignore_permissions=True)
	return _deactivate_descendants(node) if is_active == 0 else 0


def _delete_block_reason(node: Dict[str, Any]) -> Optional[str]:
	children = frappe.db.count(TREE_DOCTYPE, {PARENT_FIELD: node.name})
	if children:
		return f"'{node.node_name}' has {children} item(s) under it."
	if node.level == LEVEL_LOAN_TYPE:
		usage = count_node_usage(node.name)
		if usage["rules"] or usage["default_product"]:
			return (
				f"product assignment uses '{node.node_name}' "
				f"({usage['rules']} rule(s), default product: {'yes' if usage['default_product'] else 'no'})."
			)
	return None


def _ensure_parent_active(node: Dict[str, Any]):
	parent_id = node.get(PARENT_FIELD)
	if not parent_id:
		return
	parent = frappe.db.get_value(TREE_DOCTYPE, parent_id, ["node_name", "level", "is_active"], as_dict=True)
	if parent and not parent.is_active:
		raise frappe.ValidationError(
			f"Cannot enable '{node.node_name}': its {LEVEL_LABELS[parent.level].lower()} '{parent.node_name}' is inactive. "
			"Enable that first."
		)


def _deactivate_descendants(node: Dict[str, Any]) -> int:
	filters = descendant_filters(node)
	if not filters:
		return 0
	filters["is_active"] = 1
	descendants = frappe.get_all(TREE_DOCTYPE, filters=filters, pluck="name", limit_page_length=0)
	if descendants:
		frappe.db.set_value(TREE_DOCTYPE, {"name": ["in", descendants]}, "is_active", 0)
	return len(descendants)


def create_node(data: Dict[str, Any]) -> Dict[str, Any]:
	is_active = 1 if data.get("is_active") is None else parse_flag(data.get("is_active"), "is_active")
	node_id = _insert_node(data.get("node_name"), data.get("applicant_type"), data.get("parent_node"), is_active)
	return get_node_by_id(node_id)


def update_node(node_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	node = require_node(node_id)
	validate_update_payload(node, data)
	_update_node_fields(node_id, node_name=data["node_name"])
	return get_node_by_id(node_id)


def get_node_by_id(node_id: str) -> Dict[str, Any]:
	node = frappe.db.get_value(TREE_DOCTYPE, node_id, RETURN_FIELDS_GET_BY_ID, as_dict=True)
	if not node:
		raise frappe.DoesNotExistError(f"Loan type tree node '{node_id}' does not exist.")

	_add_names([node])
	node["children_count"] = frappe.db.count(TREE_DOCTYPE, {PARENT_FIELD: node_id})
	if node.level == LEVEL_LOAN_TYPE:
		node["usage"] = count_node_usage(node_id)
	return node


def delete_node(node_id: str):
	node = require_node(node_id)
	reason = _delete_block_reason(node)
	if reason:
		raise frappe.LinkExistsError(f"Cannot delete: {reason} Disable it instead.")
	try:
		frappe.delete_doc(TREE_DOCTYPE, node_id, ignore_permissions=True)
	except frappe.LinkExistsError:
		frappe.clear_last_message()
		raise frappe.LinkExistsError(f"Cannot delete '{node.node_name}': other records use it. Disable it instead.")


def toggle_node_status(node_id: str, is_active: int) -> Dict[str, Any]:
	node = require_node(node_id)
	ensure_status_change(node.is_active, is_active, f"{LEVEL_LABELS[node.level]} '{node.node_name}'")

	descendants_disabled = _update_node_fields(node_id, is_active=is_active)
	return {
		"name": node.name,
		"node_name": node.node_name,
		"level": node.level,
		"is_active": is_active,
		"descendants_disabled": descendants_disabled,
	}


def get_loan_types(applicant_type: Optional[str] = None, include_inactive=0) -> List[Dict[str, Any]]:
	filters = _active_filter({"level": LEVEL_LOAN_TYPE}, include_inactive)
	if applicant_type:
		filters["applicant_type"] = validate_applicant_type(applicant_type)
	return frappe.get_all(
		TREE_DOCTYPE, filters=filters, fields=RETURN_FIELDS_LOOKUP, order_by="node_name asc", limit_page_length=0
	)


def get_sub_types(loan_type: str, include_inactive=0) -> List[Dict[str, Any]]:
	_require_parent(loan_type, LEVEL_LOAN_TYPE, include_inactive)
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
	filters = _active_filter({"level": LEVEL_PURPOSE}, include_inactive)
	if sub_type:
		_require_parent(sub_type, LEVEL_SUB_TYPE, include_inactive)
		filters["sub_type"] = sub_type
	if loan_type:
		_require_parent(loan_type, LEVEL_LOAN_TYPE, include_inactive)
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


_SETUP_CHILD_KEY = {LEVEL_LOAN_TYPE: "subTypes", LEVEL_SUB_TYPE: "purposes"}


def get_setup_page(include_inactive=0) -> Dict[str, Any]:
	return {"setup": get_setup(include_inactive), "version": table_version(TREE_DOCTYPE)}


def get_setup(include_inactive=0) -> Dict[str, List[Dict[str, Any]]]:
	filters = _active_filter({}, include_inactive)
	rows = frappe.get_all(
		TREE_DOCTYPE,
		filters=filters,
		fields=["name", "node_name", "applicant_type", "level", PARENT_FIELD, "is_active"],
		order_by="level asc, creation asc",
		limit_page_length=0,
	)

	setup = {applicant_type: [] for applicant_type in APPLICANT_TYPES}
	by_id = {}
	show_active = frappe.utils.cint(include_inactive)
	for row in rows:
		item = {"id": row.name, "name": row.node_name}
		if show_active:
			item["isActive"] = row.is_active
		if row.level in _SETUP_CHILD_KEY:
			item[_SETUP_CHILD_KEY[row.level]] = []

		if row.level == LEVEL_LOAN_TYPE:
			setup[row.applicant_type].append(item)
		elif row.get(PARENT_FIELD) in by_id:
			parent = by_id[row.get(PARENT_FIELD)]
			parent["item"][_SETUP_CHILD_KEY[parent["level"]]].append(item)
		else:
			continue
		by_id[row.name] = {"item": item, "level": row.level}
	return setup


def save_setup(config: Dict[str, Any], version=None) -> Dict[str, Any]:
	check_version(version, table_version(TREE_DOCTYPE))
	applicant_types = _validate_setup_shape(config)

	existing = {
		row.name: row
		for row in frappe.get_all(
			TREE_DOCTYPE,
			filters={"applicant_type": ["in", applicant_types]},
			fields=["name", "node_name", "applicant_type", "level", PARENT_FIELD, "loan_type", "sub_type", "is_active"],
			limit_page_length=0,
		)
	}
	children_of = {}
	for row in existing.values():
		children_of.setdefault(row.get(PARENT_FIELD) or None, []).append(row)

	plan = {"create": [], "updates": [], "kept": set()}
	for applicant_type in applicant_types:
		_plan_level(config[applicant_type], LEVEL_LOAN_TYPE, applicant_type, None, "", existing, children_of, plan)

	omitted = [row for name, row in existing.items() if name not in plan["kept"]]
	_check_renames_against_omitted(plan, omitted, existing)

	summary = {"created": 0, "renamed": 0, "reactivated": 0, "deleted": 0, "deactivated": []}
	_apply_plan(plan, summary)
	_remove_omitted(omitted, summary)

	return {"setup": get_setup(), "version": table_version(TREE_DOCTYPE), "summary": summary}


def _validate_setup_shape(config) -> List[str]:
	if not isinstance(config, dict):
		raise frappe.ValidationError("Send the setup as {\"Individual\": [...], \"Business\": [...]}.")
	applicant_types = [key for key in config if key in APPLICANT_TYPES]
	unknown = [key for key in config if key not in APPLICANT_TYPES]
	if unknown:
		raise frappe.ValidationError(f"Unknown applicant type(s): {', '.join(unknown)}. Use {', '.join(APPLICANT_TYPES)}.")
	if not applicant_types:
		raise frappe.ValidationError("Send at least one applicant type: Individual or Business.")
	for applicant_type in applicant_types:
		if not isinstance(config[applicant_type], list):
			raise frappe.ValidationError(f"{applicant_type} must be a list of loan types.")
	return applicant_types


def _plan_level(items, level, applicant_type, parent_id, parent_path, existing, children_of, plan, parent_ref=None):
	label = LEVEL_LABELS[level]
	if not isinstance(items, list):
		raise frappe.ValidationError(f"{parent_path or applicant_type}: {_SETUP_CHILD_KEY[level - 1]} must be a list.")

	seen_names = set()
	for item in items:
		if not isinstance(item, dict):
			raise frappe.ValidationError(f"{parent_path or applicant_type}: each {label.lower()} must be an object.")
		name = clean_node_name(item.get("name"))
		path = f"{parent_path} > {name}" if parent_path else f"{applicant_type} > {name}"
		key = name.lower()
		if key in seen_names:
			raise frappe.ValidationError(f"{path}: the same {label.lower()} name appears twice at this level.")
		seen_names.add(key)

		node = _match_existing(item.get("id"), name, level, applicant_type, parent_id, path, existing, children_of, plan)
		if node:
			plan["kept"].add(node.name)
			rename = name if node.node_name != name else None
			reactivate = not node.is_active and item.get("id") != node.name
			if rename or reactivate:
				plan["updates"].append((node.name, rename, reactivate))
			ref = {"id": node.name}
		else:
			ref = {"id": None, "name": name, "level": level, "applicant_type": applicant_type, "parent": parent_ref or parent_id}
			plan["create"].append(ref)

		child_key = _SETUP_CHILD_KEY.get(level)
		if child_key:
			_plan_level(
				item.get(child_key) or [], level + 1, applicant_type,
				ref["id"], path, existing, children_of, plan, parent_ref=ref if not ref["id"] else None,
			)
		elif item.get("subTypes") or item.get("purposes"):
			raise frappe.ValidationError(f"{path}: a purpose cannot have anything under it.")


def _match_existing(item_id, name, level, applicant_type, parent_id, path, existing, children_of, plan):
	if item_id and item_id in existing:
		node = existing[item_id]
		if node.level != level or node.applicant_type != applicant_type or (node.get(PARENT_FIELD) or None) != parent_id:
			raise frappe.ValidationError(f"{path}: items cannot be moved to another parent, level or applicant type.")
		if node.name in plan["kept"]:
			raise frappe.ValidationError(f"{path}: the same ID appears twice.")
		return node

	if item_id and frappe.db.exists(TREE_DOCTYPE, item_id):
		raise frappe.ValidationError(f"{path}: '{item_id}' belongs to another applicant type.")

	if parent_id is not None or level == LEVEL_LOAN_TYPE:
		for sibling in children_of.get(parent_id, []):
			if (
				sibling.applicant_type == applicant_type
				and sibling.node_name.lower() == name.lower()
				and sibling.name not in plan["kept"]
			):
				return sibling
	return None


def _check_renames_against_omitted(plan, omitted, existing):
	omitted_names = {(row.get(PARENT_FIELD) or None, row.applicant_type, row.node_name.lower()) for row in omitted}
	for node_id, new_name, _ in plan["updates"]:
		if not new_name:
			continue
		node = existing[node_id]
		if (node.get(PARENT_FIELD) or None, node.applicant_type, new_name.lower()) in omitted_names:
			raise frappe.ValidationError(
				f"'{new_name}' is the name of an item you removed. Keep that item instead of renaming '{node.node_name}'."
			)


def _apply_plan(plan, summary):
	for node_id, new_name, reactivate in plan["updates"]:
		_update_node_fields(node_id, new_name, 1 if reactivate else None)
		summary["renamed"] += 1 if new_name else 0
		summary["reactivated"] += 1 if reactivate else 0

	for ref in plan["create"]:
		parent = ref["parent"]
		parent_id = parent["id"] if isinstance(parent, dict) else parent
		ref["id"] = _insert_node(ref["name"], ref["applicant_type"], parent_id)
		summary["created"] += 1


def _remove_omitted(omitted, summary):
	for row in sorted(omitted, key=lambda r: -r.level):
		node = require_node(row.name)
		if _delete_block_reason(node):
			_deactivate(node, summary)
			continue
		try:
			frappe.delete_doc(TREE_DOCTYPE, node.name, ignore_permissions=True)
			summary["deleted"] += 1
		except frappe.LinkExistsError:
			frappe.clear_last_message()
			_deactivate(node, summary)


def _deactivate(node, summary):
	_update_node_fields(node.name, is_active=0)
	summary["deactivated"].append({"id": node.name, "name": node.node_name, "level": node.level})
