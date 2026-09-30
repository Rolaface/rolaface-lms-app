from typing import Any, Dict, List

import frappe
from frappe.utils import cint

from ..common import add_date_range, load_json, parse_flag, parse_id_list
from .constant import (
	ALLOWED_UPDATE_FIELDS,
	DOCUMENT_NAME_MAX_LENGTH,
	LOAN_PRODUCT_DOCTYPE,
	MAX_DOCUMENTS,
	SETUP_DOCTYPE,
)


def validate_loan_product(data: Dict[str, Any]) -> str:
	loan_product = str(data.get("loan_product") or "").strip()
	if not loan_product:
		raise frappe.ValidationError("Loan Product is required.")

	disabled = frappe.db.get_value(LOAN_PRODUCT_DOCTYPE, loan_product, "disabled")
	if disabled is None:
		raise frappe.ValidationError(f"Loan Product '{loan_product}' does not exist.")
	if cint(disabled):
		raise frappe.ValidationError(f"Loan Product '{loan_product}' is disabled.")

	if frappe.db.exists(SETUP_DOCTYPE, loan_product):
		raise frappe.DuplicateEntryError(
			f"Documents are already set up for Loan Product '{loan_product}'. Update them instead."
		)
	return loan_product


def validate_update_payload(data: Dict[str, Any], setup_id: str):
	loan_product = data.get("loan_product")
	if loan_product not in (None, "") and str(loan_product).strip() != setup_id:
		raise frappe.ValidationError(
			"loan_product cannot be changed. Delete this setup and create one for the other product."
		)
	if not any(field in data for field in ALLOWED_UPDATE_FIELDS):
		raise frappe.ValidationError(f"Nothing to update. Send at least one of: {', '.join(sorted(ALLOWED_UPDATE_FIELDS))}.")


def validate_documents(value) -> List[Dict[str, Any]]:
	documents = load_json(value, None)
	if not isinstance(documents, list) or not documents:
		raise frappe.ValidationError("Add at least one document.")
	if len(documents) > MAX_DOCUMENTS:
		raise frappe.ValidationError(f"A product can have at most {MAX_DOCUMENTS} documents.")

	seen, cleaned = set(), []
	for index, document in enumerate(documents, start=1):
		prefix = f"Document {index}: "
		if not isinstance(document, dict):
			raise frappe.ValidationError(f"{prefix}must be an object with document_name and is_required.")

		document_name = str(document.get("document_name") or "").strip()
		if not document_name:
			raise frappe.ValidationError(f"{prefix}document_name is required.")
		if len(document_name) > DOCUMENT_NAME_MAX_LENGTH:
			raise frappe.ValidationError(f"{prefix}document_name cannot be longer than {DOCUMENT_NAME_MAX_LENGTH} characters.")
		if document_name.lower() in seen:
			raise frappe.ValidationError(f"{prefix}'{document_name}' is already in the list.")
		seen.add(document_name.lower())

		is_required = document.get("is_required")
		is_required = 1 if is_required is None else parse_flag(is_required, f"{prefix}is_required")

		cleaned.append({"document_name": document_name, "is_required": is_required})
	return cleaned


def parse_setup_row(row: Dict[str, Any]) -> Dict[str, Any]:
	documents = load_json(row.get("documents"), []) or []
	row["documents"] = documents
	row["documents_count"] = len(documents)
	row["required_count"] = sum(1 for d in documents if cint(d.get("is_required")))
	return row


def build_setup_filters(args: Dict[str, Any]) -> Dict[str, Any]:
	filters = {}

	ids = parse_id_list(args.get("ids"))
	if ids:
		filters["name"] = ["in", ids]

	add_date_range(filters, args)
	return filters
