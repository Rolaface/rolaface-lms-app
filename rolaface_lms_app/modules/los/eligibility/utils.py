from typing import Any, Dict

import frappe

from ..common import dump_json, load_json
from .constant import COLLATERAL_KEYS, FORMULA_KEYS, FREE_FORM_SECTIONS, RULE_NAME_MAX_LENGTH, SECTIONS


def clean_rule_name(value) -> str:
	name = str(value or "").strip()
	if not name:
		raise frappe.ValidationError("Rule Name is required.")
	if len(name) > RULE_NAME_MAX_LENGTH:
		raise frappe.ValidationError(f"Rule Name cannot be longer than {RULE_NAME_MAX_LENGTH} characters.")
	return name


def sections_to_save(data: Dict[str, Any]) -> Dict[str, Any]:
	return {field: dump_json(_clean_section(field, data[field])) for field in SECTIONS if field in data}


def _clean_section(field: str, value):
	value = load_json(value, None)
	if value is None:
		return None

	expected = SECTIONS[field]
	if not isinstance(value, expected):
		raise frappe.ValidationError(f"{field} must be {'a list' if expected is list else 'an object'}.")
	if field in FREE_FORM_SECTIONS:
		return value
	if expected is list and not all(isinstance(item, dict) for item in value):
		raise frappe.ValidationError(f"{field}: every item must be an object.")
	if field == "collateral_items":
		return [{key: item.get(key) for key in COLLATERAL_KEYS} for item in value]
	if field == "formula_params":
		return {key: value[key] for key in FORMULA_KEYS if key in value}
	return value


def parse_sections(row: Dict[str, Any]) -> Dict[str, Any]:
	for field in SECTIONS:
		if field in row:
			row[field] = load_json(row[field], None)
	return row
