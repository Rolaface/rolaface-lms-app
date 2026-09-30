from typing import Any, Dict, List, Tuple

import frappe
from frappe.utils import now_datetime

from .. import versioned
from ..common import dump_json, load_json
from .constant import (
	ACTIONS,
	ALLOWED_UPDATE_FIELDS,
	COPY_TO_DRAFT_FIELDS,
	DATE_UNITS,
	FIELDS,
	OPERATORS,
	RETURN_FIELDS,
	RULESET_DOCTYPE,
	RULESET_LABEL,
	RULESET_NAME_MAX_LENGTH,
	SEVERITIES,
)
from .utils import clean_ruleset_name, count_rules, evaluate, normalize_groups


def _get_row(ruleset_id: str) -> Dict[str, Any]:
	return versioned.get_row(RULESET_DOCTYPE, ruleset_id, RETURN_FIELDS, "Pre-screening rule set")


def _present(row: Dict[str, Any], with_groups: bool = True) -> Dict[str, Any]:
	groups = load_json(row.get("groups"), []) or []
	row["rules_count"] = count_rules(groups)
	if with_groups:
		row["groups"] = groups
	else:
		row.pop("groups", None)
	return row


def get_ruleset(ruleset_id: str) -> Dict[str, Any]:
	row = _present(_get_row(ruleset_id))
	row["draft_id"] = versioned.draft_id(RULESET_DOCTYPE, row)
	return versioned.add_product_names([row])[0]


def get_rulesets(args: Dict[str, Any], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int]:
	fields = ["name", "ruleset_name", "loan_product", "version", "status", "effective_from", "groups", "modified", "modified_by"]
	rows, total = versioned.list_per_product(RULESET_DOCTYPE, fields, args, page, page_size, ["ruleset_name", "loan_product"])
	return versioned.add_product_names([_present(row, with_groups=False) for row in rows]), total


def get_ruleset_versions(loan_product: str) -> List[Dict[str, Any]]:
	fields = ["name", "version", "status", "effective_from", "effective_to", "groups", "published_by", "published_on", "modified", "modified_by"]
	return [_present(row, with_groups=False) for row in versioned.product_versions(RULESET_DOCTYPE, loan_product, fields)]


def get_prescreening_fields() -> Dict[str, Any]:
	return {
		"fields": [{"id": field_id, **spec} for field_id, spec in FIELDS.items()],
		"operators": OPERATORS,
		"severities": [{"severity": severity, "default_action": action} for severity, action in SEVERITIES.items()],
		"actions": ACTIONS,
		"date_units": DATE_UNITS,
	}


def test_ruleset(ruleset_id: str, facts) -> Dict[str, Any]:
	row = _get_row(ruleset_id)
	facts = load_json(facts, {}) or {}
	if not isinstance(facts, dict):
		raise frappe.ValidationError("facts must be an object of {field: value}.")

	result = evaluate(normalize_groups(row.groups), facts)
	return {"name": row.name, "version": row.version, "status": row.status, **result}


def create_ruleset(data: Dict[str, Any]) -> Dict[str, Any]:
	loan_product = versioned.ensure_new_product(RULESET_DOCTYPE, data.get("loan_product"), RULESET_LABEL)
	effective_from, effective_to = versioned.clean_dates(data.get("effective_from"), data.get("effective_to"))

	doc = frappe.new_doc(RULESET_DOCTYPE)
	doc.update(
		{
			"ruleset_name": clean_ruleset_name(data.get("ruleset_name"), RULESET_NAME_MAX_LENGTH),
			"loan_product": loan_product,
			"description": data.get("description"),
			"version": versioned.FIRST_VERSION,
			"status": versioned.DRAFT,
			"effective_from": effective_from,
			"effective_to": effective_to,
			"groups": dump_json(normalize_groups(data.get("groups"))),
		}
	)
	doc.insert(ignore_permissions=True)
	return get_ruleset(doc.name)


def update_ruleset(ruleset_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	row = _get_row(ruleset_id)
	fixed = [field for field in ("status", "version", "loan_product") if field in data]
	if fixed:
		raise frappe.ValidationError(f"{', '.join(fixed)} cannot be changed here. Use set_ruleset_status for status.")
	if not any(field in data for field in ALLOWED_UPDATE_FIELDS):
		raise frappe.ValidationError(f"Nothing to update. Send at least one of: {', '.join(sorted(ALLOWED_UPDATE_FIELDS))}.")

	doc = frappe.get_doc(RULESET_DOCTYPE, versioned.editable_draft(RULESET_DOCTYPE, row, COPY_TO_DRAFT_FIELDS))
	if "ruleset_name" in data:
		doc.ruleset_name = clean_ruleset_name(data.get("ruleset_name"), RULESET_NAME_MAX_LENGTH)
	if "description" in data:
		doc.description = data.get("description")
	if "groups" in data:
		doc.groups = dump_json(normalize_groups(data.get("groups")))
	versioned.apply_dates(doc, data)
	doc.save(ignore_permissions=True)
	return get_ruleset(doc.name)


def set_ruleset_status(ruleset_id: str, status) -> Dict[str, Any]:
	versioned.set_status(RULESET_DOCTYPE, _get_row(ruleset_id), status, before_publish=_check_and_stamp)
	return get_ruleset(ruleset_id)


def _check_and_stamp(doc):
	doc.groups = dump_json(normalize_groups(doc.groups, complete=True))
	doc.published_by = frappe.session.user
	doc.published_on = now_datetime()


def delete_ruleset(ruleset_id: str):
	versioned.delete_draft(RULESET_DOCTYPE, _get_row(ruleset_id))
