from typing import Any, Dict, Optional

import frappe

from ..common import json_contains, load_json, validate_update_fields
from .constant import (
	ALLOWED_UPDATE_FIELDS,
	APPLICANT_TYPES,
	LEVEL_LABELS,
	LEVEL_LOAN_TYPE,
	LEVEL_PURPOSE,
	LEVEL_SUB_TYPE,
	NODE_NAME_MAX_LENGTH,
	PARENT_FIELD,
	RULE_DOCTYPE,
	SET_ONCE_FIELDS,
	SETTINGS_DOCTYPE,
	TREE_DOCTYPE,
)

NODE_STATE_FIELDS = ["name", "node_name", "applicant_type", "level", PARENT_FIELD, "loan_type", "sub_type", "is_active"]


def get_node_state(node_id: str) -> Optional[Dict[str, Any]]:
	return frappe.db.get_value(TREE_DOCTYPE, node_id, NODE_STATE_FIELDS, as_dict=True)


def require_node(node_id: str, expected_level: Optional[int] = None, label: Optional[str] = None) -> Dict[str, Any]:
	node = get_node_state(node_id)
	label = label or (LEVEL_LABELS[expected_level] if expected_level else "Node")
	if not node:
		raise frappe.DoesNotExistError(f"{label} '{node_id}' does not exist.")
	if expected_level and node.level != expected_level:
		raise frappe.ValidationError(f"'{node.node_name}' is a {LEVEL_LABELS.get(node.level, 'node')}, not a {label}.")
	return node


def clean_node_name(value) -> str:
	node_name = str(value or "").strip()
	if not node_name:
		raise frappe.ValidationError("Name is required.")
	if len(node_name) > NODE_NAME_MAX_LENGTH:
		raise frappe.ValidationError(f"Name cannot be longer than {NODE_NAME_MAX_LENGTH} characters.")
	return node_name


def validate_applicant_type(value) -> str:
	if value not in APPLICANT_TYPES:
		raise frappe.ValidationError(f"Applicant Type must be one of: {', '.join(APPLICANT_TYPES)}.")
	return value


def ensure_unique_name(node_name: str, applicant_type: str, parent: Optional[str], node_id: Optional[str] = None):
	# Same name is allowed under different parents ("Other"), never twice under one parent.
	filters = {
		"node_name": node_name,
		"applicant_type": applicant_type,
		PARENT_FIELD: parent if parent else ["is", "not set"],
	}
	if node_id:
		filters["name"] = ["!=", node_id]
	if frappe.db.exists(TREE_DOCTYPE, filters):
		raise frappe.DuplicateEntryError(f"'{node_name}' already exists at this level.")


def resolve_hierarchy(data: Dict[str, Any]) -> Dict[str, Any]:
	"""Works out level, applicant type and ancestors from the parent, so callers can't send wrong values."""
	parent_id = str(data.get("parent_node") or "").strip() or None

	if not parent_id:
		return {
			"applicant_type": validate_applicant_type(data.get("applicant_type")),
			"level": LEVEL_LOAN_TYPE,
			"parent": None,
			"loan_type": None,
			"sub_type": None,
		}

	parent = require_node(parent_id, label="Parent")
	if parent.level >= LEVEL_PURPOSE:
		raise frappe.ValidationError("A purpose cannot have anything under it.")
	if not parent.is_active:
		raise frappe.ValidationError(f"Cannot add under the inactive {LEVEL_LABELS[parent.level].lower()} '{parent.node_name}'.")
	if data.get("applicant_type") and data.get("applicant_type") != parent.applicant_type:
		raise frappe.ValidationError(
			f"Applicant Type must match the parent ({parent.applicant_type}). Leave it out to copy it from the parent."
		)

	# Store ancestors only: a sub-type points at its loan type, a purpose at both.
	if parent.level == LEVEL_LOAN_TYPE:
		loan_type, sub_type = parent.name, None
	else:
		loan_type, sub_type = parent.loan_type, parent.name

	return {
		"applicant_type": parent.applicant_type,
		"level": parent.level + 1,
		"parent": parent.name,
		"loan_type": loan_type,
		"sub_type": sub_type,
	}


def validate_update_payload(node: Dict[str, Any], data: Dict[str, Any]):
	current = {"applicant_type": node.applicant_type, "parent_node": node.get(PARENT_FIELD)}
	for field in SET_ONCE_FIELDS:
		if field in data and (data.get(field) or None) != (current[field] or None):
			raise frappe.ValidationError(
				f"{field} cannot be changed after creation. Create a new node and disable this one instead."
			)

	validate_update_fields(data, ALLOWED_UPDATE_FIELDS, "node")
	data["node_name"] = clean_node_name(data.get("node_name"))
	ensure_unique_name(data["node_name"], node.applicant_type, node.get(PARENT_FIELD), node.name)


def descendant_filters(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if node.level == LEVEL_LOAN_TYPE:
		return {"loan_type": node.name}
	if node.level == LEVEL_SUB_TYPE:
		return {"sub_type": node.name}
	return None


def count_node_usage(node_id: str) -> Dict[str, int]:
	"""Where a loan type is referenced by value (JSON), which Frappe's link checks can't see."""
	rules = frappe.db.count(RULE_DOCTYPE, filters=[json_contains("loan_types", node_id)])
	defaults = load_json(frappe.db.get_single_value(SETTINGS_DOCTYPE, "default_product"), {}) or {}
	return {"rules": rules, "default_product": 1 if node_id in defaults else 0}
