from typing import Any, Dict, List, Tuple

import frappe

from .. import versioned
from .constant import (
	ALLOWED_UPDATE_FIELDS,
	COPY_TO_DRAFT_FIELDS,
	LIST_FIELDS,
	RETURN_FIELDS,
	RULE_DOCTYPE,
	RULE_LABEL,
)
from .utils import clean_rule_name, parse_sections, sections_to_save


def _get_row(rule_id: str) -> Dict[str, Any]:
	return versioned.get_row(RULE_DOCTYPE, rule_id, RETURN_FIELDS, "Eligibility rule")


def get_eligibility_rule(rule_id: str) -> Dict[str, Any]:
	row = parse_sections(_get_row(rule_id))
	row["draft_id"] = versioned.draft_id(RULE_DOCTYPE, row)
	return versioned.add_product_names([row])[0]


def get_eligibility_rules(args: Dict[str, Any], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int]:
	rows, total = versioned.list_per_product(RULE_DOCTYPE, LIST_FIELDS, args, page, page_size, ["rule_name", "loan_product"])
	return versioned.add_product_names(rows), total


def get_eligibility_rule_versions(loan_product: str) -> List[Dict[str, Any]]:
	return versioned.product_versions(RULE_DOCTYPE, loan_product, LIST_FIELDS)


def create_eligibility_rule(data: Dict[str, Any]) -> Dict[str, Any]:
	loan_product = versioned.ensure_new_product(RULE_DOCTYPE, data.get("loan_product"), RULE_LABEL)
	effective_from, effective_to = versioned.clean_dates(data.get("effective_from"), data.get("effective_to"))

	doc = frappe.new_doc(RULE_DOCTYPE)
	doc.update(
		{
			"rule_name": clean_rule_name(data.get("rule_name")),
			"loan_product": loan_product,
			"version": versioned.FIRST_VERSION,
			"status": versioned.DRAFT,
			"effective_from": effective_from,
			"effective_to": effective_to,
			**sections_to_save(data),
		}
	)
	doc.insert(ignore_permissions=True)
	return get_eligibility_rule(doc.name)


def update_eligibility_rule(rule_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	row = _get_row(rule_id)
	fixed = [field for field in ("status", "version", "loan_product") if field in data]
	if fixed:
		raise frappe.ValidationError(f"{', '.join(fixed)} cannot be changed here. Use set_eligibility_rule_status for status.")
	if not any(field in data for field in ALLOWED_UPDATE_FIELDS):
		raise frappe.ValidationError(f"Nothing to update. Send at least one of: {', '.join(sorted(ALLOWED_UPDATE_FIELDS))}.")

	doc = frappe.get_doc(RULE_DOCTYPE, versioned.editable_draft(RULE_DOCTYPE, row, COPY_TO_DRAFT_FIELDS))
	if "rule_name" in data:
		doc.rule_name = clean_rule_name(data.get("rule_name"))
	doc.update(sections_to_save(data))
	versioned.apply_dates(doc, data)
	doc.save(ignore_permissions=True)
	return get_eligibility_rule(doc.name)


def set_eligibility_rule_status(rule_id: str, status) -> Dict[str, Any]:
	versioned.set_status(RULE_DOCTYPE, _get_row(rule_id), status)
	return get_eligibility_rule(rule_id)


def delete_eligibility_rule(rule_id: str):
	versioned.delete_draft(RULE_DOCTYPE, _get_row(rule_id))
