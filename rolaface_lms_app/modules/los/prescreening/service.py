from typing import Any, Dict, List, Tuple

import frappe
from frappe.utils import now_datetime, nowdate

from ..common import dump_json, load_json, name_map, search_or_filters
from .constant import (
	ACTIONS,
	ALLOWED_UPDATE_FIELDS,
	DATE_UNITS,
	FIELDS,
	LIST_STATUS_ORDER,
	LOAN_PRODUCT_DOCTYPE,
	OPERATORS,
	RETURN_FIELDS,
	RULESET_DOCTYPE,
	RULESET_NAME_MAX_LENGTH,
	SETTABLE_STATUSES,
	SEVERITIES,
	STATUS_ACTIVE,
	STATUS_ARCHIVED,
	STATUS_DRAFT,
	STATUS_INACTIVE,
)
from .utils import clean_ruleset_name, count_rules, evaluate, next_version, normalize_groups

# Each row is one version of one loan product's rule set. A product has at most one Draft
# and one live (Active or Inactive) version; older ones are Archived.


def _get_row(ruleset_id: str) -> Dict[str, Any]:
	row = frappe.db.get_value(RULESET_DOCTYPE, ruleset_id, RETURN_FIELDS, as_dict=True)
	if not row:
		raise frappe.DoesNotExistError(f"Pre-screening rule set '{ruleset_id}' does not exist.")
	return row


def _product_rows(loan_product: str, statuses=None) -> List[Dict[str, Any]]:
	filters = {"loan_product": loan_product}
	if statuses:
		filters["status"] = ["in", list(statuses)]
	return frappe.get_all(
		RULESET_DOCTYPE, filters=filters, fields=["name", "version", "status", "effective_from"], order_by="creation desc"
	)


def _present(row: Dict[str, Any], with_groups: bool = True) -> Dict[str, Any]:
	groups = load_json(row.get("groups"), []) or []
	row["rules_count"] = count_rules(groups)
	if with_groups:
		row["groups"] = groups
	else:
		row.pop("groups", None)
	return row


def _add_product_names(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	names = name_map(LOAN_PRODUCT_DOCTYPE, [r["loan_product"] for r in rows], "product_name")
	for row in rows:
		row["product_name"] = names.get(row["loan_product"])
	return rows


# ---------------------------------------------------------------- Reads


def get_ruleset(ruleset_id: str) -> Dict[str, Any]:
	row = _present(_get_row(ruleset_id))
	draft = _product_rows(row.loan_product, [STATUS_DRAFT])
	row["draft"] = draft[0].name if draft and draft[0].name != row.name else None
	return _add_product_names([row])[0]


def get_rulesets(args: Dict[str, Any], page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int]:
	"""One line per loan product: its live version, else its draft."""
	filters = {"status": ["!=", STATUS_ARCHIVED]}
	if args.get("loan_product"):
		filters["loan_product"] = args.get("loan_product")
	rows = frappe.get_all(
		RULESET_DOCTYPE,
		filters=filters,
		or_filters=search_or_filters(args.get("search"), ["ruleset_name", "loan_product"]) or None,
		fields=["name", "ruleset_name", "loan_product", "version", "status", "effective_from", "groups", "modified", "modified_by"],
		order_by="modified desc",
		limit_page_length=0,
	)

	by_product: Dict[str, List[Dict[str, Any]]] = {}
	for row in rows:
		by_product.setdefault(row.loan_product, []).append(row)

	summaries = []
	for product_rows in by_product.values():
		shown = min(product_rows, key=lambda r: LIST_STATUS_ORDER.index(r.status))
		draft = next((r.name for r in product_rows if r.status == STATUS_DRAFT and r.name != shown.name), None)
		summaries.append({**_present(shown, with_groups=False), "draft": draft})

	if args.get("status"):
		summaries = [s for s in summaries if s["status"] == args.get("status")]
	summaries.sort(key=lambda s: s["modified"], reverse=True)

	total = len(summaries)
	page_rows = summaries[(page - 1) * page_size : page * page_size]
	return _add_product_names(page_rows), total


def get_ruleset_versions(loan_product: str) -> List[Dict[str, Any]]:
	"""Every version of a product's rule set, newest first (Versions tab)."""
	rows = frappe.get_all(
		RULESET_DOCTYPE,
		filters={"loan_product": loan_product},
		fields=["name", "version", "status", "effective_from", "effective_to", "groups", "published_by", "published_on", "modified", "modified_by"],
		order_by="creation desc",
		limit_page_length=0,
	)
	return [_present(row, with_groups=False) for row in rows]


def get_prescreening_fields() -> Dict[str, Any]:
	"""Everything the rule builder's dropdowns need, from the same lists the backend validates against."""
	return {
		"fields": [{"id": field_id, **spec} for field_id, spec in FIELDS.items()],
		"operators": OPERATORS,
		"severities": [{"severity": severity, "default_action": action} for severity, action in SEVERITIES.items()],
		"actions": ACTIONS,
		"date_units": DATE_UNITS,
	}


def test_ruleset(ruleset_id: str, facts) -> Dict[str, Any]:
	"""
	Runs sample applicant values through any version, drafts included (Test tab).
	facts is {field: value}; fields without a value, and unfinished rules, are reported as not checked.
	"""
	row = _get_row(ruleset_id)
	facts = load_json(facts, {}) or {}
	if not isinstance(facts, dict):
		raise frappe.ValidationError("facts must be an object of {field: value}.")

	result = evaluate(normalize_groups(row.groups), facts)
	return {"name": row.name, "version": row.version, "status": row.status, **result}


# ---------------------------------------------------------------- Writes


def create_ruleset(data: Dict[str, Any]) -> Dict[str, Any]:
	loan_product = str(data.get("loan_product") or "").strip()
	if not loan_product:
		raise frappe.ValidationError("Loan Product is required.")
	product = frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, loan_product, ["name", "disabled"], as_dict=True)
	if not product:
		raise frappe.DoesNotExistError(f"Loan Product '{loan_product}' does not exist.")
	if product.disabled:
		raise frappe.ValidationError(f"Loan Product '{loan_product}' is disabled.")
	if frappe.db.exists(RULESET_DOCTYPE, {"loan_product": loan_product}):
		raise frappe.DuplicateEntryError(f"Loan Product '{loan_product}' already has a pre-screening rule set.")

	doc = frappe.new_doc(RULESET_DOCTYPE)
	doc.update(
		{
			"ruleset_name": clean_ruleset_name(data.get("ruleset_name"), RULESET_NAME_MAX_LENGTH),
			"loan_product": loan_product,
			"description": data.get("description"),
			"version": next_version([]),
			"status": STATUS_DRAFT,
			"groups": dump_json(normalize_groups(data.get("groups"))),
		}
	)
	doc.insert(ignore_permissions=True)
	return get_ruleset(doc.name)


def update_ruleset(ruleset_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Save Draft. Only a Draft is ever edited: editing a published version saves into the product's Draft,
	creating it from that version first if there isn't one. The response is the Draft.
	"""
	row = _get_row(ruleset_id)
	fixed = [field for field in ("status", "version", "loan_product", "effective_from") if field in data]
	if fixed:
		raise frappe.ValidationError(f"{', '.join(fixed)} cannot be changed here; status and effective date are set by set_ruleset_status.")
	if not any(field in data for field in ALLOWED_UPDATE_FIELDS):
		raise frappe.ValidationError(f"Nothing to update. Send at least one of: {', '.join(sorted(ALLOWED_UPDATE_FIELDS))}.")
	if row.status == STATUS_ARCHIVED:
		raise frappe.ValidationError(f"Version {row.version} is archived and cannot be edited.")

	doc = frappe.get_doc(RULESET_DOCTYPE, _draft_for(row))
	if "ruleset_name" in data:
		doc.ruleset_name = clean_ruleset_name(data.get("ruleset_name"), RULESET_NAME_MAX_LENGTH)
	if "description" in data:
		doc.description = data.get("description")
	if "groups" in data:
		doc.groups = dump_json(normalize_groups(data.get("groups")))
	doc.save(ignore_permissions=True)
	return get_ruleset(doc.name)


def _draft_for(row: Dict[str, Any]) -> str:
	if row.status == STATUS_DRAFT:
		return row.name
	existing = _product_rows(row.loan_product, [STATUS_DRAFT])
	if existing:
		return existing[0].name

	draft = frappe.new_doc(RULESET_DOCTYPE)
	draft.update(
		{
			"ruleset_name": row.ruleset_name,
			"loan_product": row.loan_product,
			"description": row.description,
			"version": next_version([r.version for r in _product_rows(row.loan_product)]),
			"status": STATUS_DRAFT,
			"groups": row.groups,
		}
	)
	draft.insert(ignore_permissions=True)
	return draft.name


def set_ruleset_status(ruleset_id: str, status) -> Dict[str, Any]:
	"""
	Active: publishes a draft, or switches an inactive version back on.
	Inactive: switches the active version off; applications for the product skip pre-screening.
	"""
	if status not in SETTABLE_STATUSES:
		raise frappe.ValidationError(f"status must be one of: {', '.join(SETTABLE_STATUSES)}.")

	row = _get_row(ruleset_id)
	if row.status == status:
		raise frappe.ValidationError(f"Version {row.version} is already {status.lower()}.")

	if status == STATUS_INACTIVE:
		if row.status != STATUS_ACTIVE:
			raise frappe.ValidationError(f"Version {row.version} is {row.status.lower()}; only an active version can be deactivated.")
		_set_status(row.name, STATUS_INACTIVE)
	elif row.status == STATUS_INACTIVE:
		_set_status(row.name, STATUS_ACTIVE)
	elif row.status == STATUS_DRAFT:
		_publish(row)
	else:
		raise frappe.ValidationError(f"Version {row.version} is {row.status.lower()}; only a draft or an inactive version can be activated.")
	return get_ruleset(row.name)


def _publish(row: Dict[str, Any]):
	"""The draft goes live today; the previous live version is archived."""
	doc = frappe.get_doc(RULESET_DOCTYPE, row.name)
	doc.groups = dump_json(normalize_groups(doc.groups, complete=True))
	_archive_live(row.loan_product)
	doc.status = STATUS_ACTIVE
	doc.effective_from = nowdate()
	doc.published_by = frappe.session.user
	doc.published_on = now_datetime()
	doc.save(ignore_permissions=True)


def delete_ruleset(ruleset_id: str):
	"""Only a draft can be deleted; versions that have been live are kept as history."""
	row = _get_row(ruleset_id)
	if row.status != STATUS_DRAFT:
		raise frappe.LinkExistsError(f"Version {row.version} has been live and is kept as history. Deactivate it instead.")
	frappe.delete_doc(RULESET_DOCTYPE, row.name, ignore_permissions=True)


def _archive_live(loan_product: str):
	for live in _product_rows(loan_product, [STATUS_ACTIVE, STATUS_INACTIVE]):
		doc = frappe.get_doc(RULESET_DOCTYPE, live.name)
		doc.status = STATUS_ARCHIVED
		doc.effective_to = nowdate()
		doc.save(ignore_permissions=True)


def _set_status(ruleset_id: str, status: str):
	# Save the document (not db.set_value) so the change shows in its history.
	doc = frappe.get_doc(RULESET_DOCTYPE, ruleset_id)
	doc.status = status
	doc.save(ignore_permissions=True)
