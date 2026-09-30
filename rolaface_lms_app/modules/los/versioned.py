from typing import Any, Callable, Dict, List, Optional, Tuple

import frappe
from frappe.utils import nowdate

from .common import name_map, search_or_filters

LOAN_PRODUCT_DOCTYPE = "Loan Product"

DRAFT = "Draft"
ACTIVE = "Active"
INACTIVE = "Inactive"
ARCHIVED = "Archived"
SETTABLE_STATUSES = (ACTIVE, INACTIVE)
LIST_STATUS_ORDER = (ACTIVE, INACTIVE, DRAFT)
FIRST_VERSION = "1.0"


def get_row(doctype: str, name: str, fields: List[str], label: str) -> Dict[str, Any]:
	row = frappe.db.get_value(doctype, name, fields, as_dict=True)
	if not row:
		raise frappe.DoesNotExistError(f"{label} '{name}' does not exist.")
	return row


def product_rows(doctype: str, loan_product: str, statuses=None) -> List[Dict[str, Any]]:
	filters = {"loan_product": loan_product}
	if statuses:
		filters["status"] = ["in", list(statuses)]
	return frappe.get_all(doctype, filters=filters, fields=["name", "version", "status"], order_by="creation desc")


def draft_id(doctype: str, row: Dict[str, Any]) -> Optional[str]:
	drafts = product_rows(doctype, row["loan_product"], [DRAFT])
	return drafts[0].name if drafts and drafts[0].name != row["name"] else None


def add_product_names(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	names = name_map(LOAN_PRODUCT_DOCTYPE, [r["loan_product"] for r in rows], "product_name")
	for row in rows:
		row["product_name"] = names.get(row["loan_product"])
	return rows


def list_per_product(
	doctype: str, fields: List[str], args: Dict[str, Any], page: int, page_size: int, search_fields: List[str]
) -> Tuple[List[Dict[str, Any]], int]:
	filters = {"status": ["!=", ARCHIVED]}
	if args.get("loan_product"):
		filters["loan_product"] = args.get("loan_product")
	rows = frappe.get_all(
		doctype,
		filters=filters,
		or_filters=search_or_filters(args.get("search"), search_fields) or None,
		fields=list({*fields, "name", "loan_product", "status", "modified"}),
		order_by="modified desc",
		limit_page_length=0,
	)

	by_product: Dict[str, List[Dict[str, Any]]] = {}
	for row in rows:
		by_product.setdefault(row.loan_product, []).append(row)

	lines = []
	for versions in by_product.values():
		shown = min(versions, key=lambda r: LIST_STATUS_ORDER.index(r.status))
		shown["draft_id"] = next((r.name for r in versions if r.status == DRAFT and r.name != shown.name), None)
		lines.append(shown)

	if args.get("status"):
		lines = [line for line in lines if line.status == args.get("status")]
	lines.sort(key=lambda line: line.modified, reverse=True)
	return lines[(page - 1) * page_size : page * page_size], len(lines)


def product_versions(doctype: str, loan_product: str, fields: List[str]) -> List[Dict[str, Any]]:
	if not loan_product:
		raise frappe.ValidationError("loan_product is required.")
	return frappe.get_all(doctype, filters={"loan_product": loan_product}, fields=fields, order_by="creation desc", limit_page_length=0)


def ensure_new_product(doctype: str, loan_product, label: str) -> str:
	loan_product = str(loan_product or "").strip()
	if not loan_product:
		raise frappe.ValidationError("Loan Product is required.")
	product = frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, loan_product, ["name", "disabled"], as_dict=True)
	if not product:
		raise frappe.DoesNotExistError(f"Loan Product '{loan_product}' does not exist.")
	if product.disabled:
		raise frappe.ValidationError(f"Loan Product '{loan_product}' is disabled.")
	if frappe.db.exists(doctype, {"loan_product": loan_product}):
		raise frappe.DuplicateEntryError(f"Loan Product '{loan_product}' already has {label}.")
	return loan_product


def editable_draft(doctype: str, row: Dict[str, Any], copy_fields: List[str]) -> str:
	if row["status"] == DRAFT:
		return row["name"]
	if row["status"] == ARCHIVED:
		raise frappe.ValidationError(f"Version {row['version']} is archived and cannot be edited.")

	existing = product_rows(doctype, row["loan_product"], [DRAFT])
	if existing:
		return existing[0].name

	draft = frappe.new_doc(doctype)
	draft.update({field: row.get(field) for field in copy_fields})
	draft.update(
		{
			"loan_product": row["loan_product"],
			"version": next_version([r.version for r in product_rows(doctype, row["loan_product"])]),
			"status": DRAFT,
		}
	)
	draft.insert(ignore_permissions=True)
	return draft.name


def set_status(doctype: str, row: Dict[str, Any], status, before_publish: Optional[Callable] = None):
	if status not in SETTABLE_STATUSES:
		raise frappe.ValidationError(f"status must be one of: {', '.join(SETTABLE_STATUSES)}.")
	current, version = row["status"], row["version"]
	if current == status:
		raise frappe.ValidationError(f"Version {version} is already {status.lower()}.")

	if status == INACTIVE:
		if current != ACTIVE:
			raise frappe.ValidationError(f"Version {version} is {current.lower()}; only an active version can be deactivated.")
		_save_status(doctype, row["name"], INACTIVE)
	elif current == INACTIVE:
		_save_status(doctype, row["name"], ACTIVE)
	elif current == DRAFT:
		_publish(doctype, row, before_publish)
	else:
		raise frappe.ValidationError(f"Version {version} is {current.lower()}; only a draft or an inactive version can be activated.")


def delete_draft(doctype: str, row: Dict[str, Any]):
	if row["status"] != DRAFT:
		raise frappe.LinkExistsError(f"Version {row['version']} has been live and is kept as history. Deactivate it instead.")
	frappe.delete_doc(doctype, row["name"], ignore_permissions=True)


def _publish(doctype: str, row: Dict[str, Any], before_publish: Optional[Callable]):
	doc = frappe.get_doc(doctype, row["name"])
	if before_publish:
		before_publish(doc)
	for live in product_rows(doctype, row["loan_product"], [ACTIVE, INACTIVE]):
		old = frappe.get_doc(doctype, live.name)
		old.status = ARCHIVED
		old.effective_to = old.effective_to or nowdate()
		old.save(ignore_permissions=True)
	doc.status = ACTIVE
	doc.effective_from = doc.effective_from or nowdate()
	doc.save(ignore_permissions=True)


def _save_status(doctype: str, name: str, status: str):
	doc = frappe.get_doc(doctype, name)
	doc.status = status
	doc.save(ignore_permissions=True)


def next_version(versions: List[str]) -> str:
	tenths = [_tenths(v) for v in versions if v]
	if not tenths:
		return FIRST_VERSION
	nxt = max(tenths) + 1
	return f"{nxt // 10}.{nxt % 10}"


def _tenths(version: str) -> int:
	major, _, minor = str(version).partition(".")
	return int(major or 0) * 10 + int((minor or "0")[:1])


def clean_dates(effective_from, effective_to) -> Tuple[Optional[str], Optional[str]]:
	dates = []
	for value, label in ((effective_from, "Effective From"), (effective_to, "Effective To")):
		if value is None or str(value).strip() == "":
			dates.append(None)
			continue
		try:
			dates.append(frappe.utils.getdate(value).isoformat())
		except Exception:
			raise frappe.ValidationError(f"{label} must be a date (YYYY-MM-DD).")
	if dates[0] and dates[1] and dates[1] < dates[0]:
		raise frappe.ValidationError("Effective To cannot be before Effective From.")
	return dates[0], dates[1]


def apply_dates(doc, data: Dict[str, Any]):
	if "effective_from" in data or "effective_to" in data:
		doc.effective_from, doc.effective_to = clean_dates(
			data["effective_from"] if "effective_from" in data else doc.effective_from,
			data["effective_to"] if "effective_to" in data else doc.effective_to,
		)
