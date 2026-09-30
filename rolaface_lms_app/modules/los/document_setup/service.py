from typing import Any, Dict, List, Tuple

import frappe

from ..common import build_order_by, count_records, dump_json, search_or_filters
from .constant import (
	ALLOWED_SORT_FIELDS,
	LOAN_PRODUCT_DOCTYPE,
	PRODUCT_SEARCH_FIELDS,
	RETURN_FIELDS_GET_ALL,
	RETURN_FIELDS_GET_BY_ID,
	SEARCH_FIELDS,
	SETUP_DOCTYPE,
)
from .utils import build_setup_filters, parse_setup_row, validate_documents, validate_loan_product, validate_update_payload


def _ensure_exists(setup_id: str):
	if not frappe.db.exists(SETUP_DOCTYPE, setup_id):
		raise frappe.DoesNotExistError(f"No documents are set up for Loan Product '{setup_id}'.")


def create_document_setup(data: Dict[str, Any]) -> Dict[str, Any]:
	loan_product = validate_loan_product(data)
	documents = validate_documents(data.get("documents"))

	setup_doc = frappe.new_doc(SETUP_DOCTYPE)
	setup_doc.loan_product = loan_product
	setup_doc.documents = dump_json(documents)
	setup_doc.insert(ignore_permissions=True)
	return get_document_setup_by_id(setup_doc.name)


def update_document_setup(setup_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	_ensure_exists(setup_id)
	validate_update_payload(data, setup_id)

	setup_doc = frappe.get_doc(SETUP_DOCTYPE, setup_id)
	setup_doc.documents = dump_json(validate_documents(data.get("documents")))
	setup_doc.save(ignore_permissions=True)
	return get_document_setup_by_id(setup_id)


def get_document_setup_by_id(setup_id: str) -> Dict[str, Any]:
	setup = frappe.db.get_value(SETUP_DOCTYPE, setup_id, RETURN_FIELDS_GET_BY_ID, as_dict=True)
	if not setup:
		raise frappe.DoesNotExistError(f"No documents are set up for Loan Product '{setup_id}'.")
	return parse_setup_row(setup)


def get_document_setups(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int, int]:
	filters = build_setup_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS)
	order_by = build_order_by(SETUP_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS)

	setups = frappe.get_all(
		SETUP_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)

	total_records = count_records(SETUP_DOCTYPE, filters, or_filters)
	total_pages = (total_records + page_size - 1) // page_size
	return [parse_setup_row(s) for s in setups], total_records, total_pages


def get_products_without_documents(args: Dict[str, Any]) -> List[Dict[str, Any]]:
	configured = frappe.get_all(SETUP_DOCTYPE, pluck="name", limit_page_length=0)

	filters = {"disabled": 0}
	if configured:
		filters["name"] = ["not in", configured]

	return frappe.get_all(
		LOAN_PRODUCT_DOCTYPE,
		filters=filters,
		or_filters=search_or_filters(args.get("search"), PRODUCT_SEARCH_FIELDS) or None,
		fields=["name", "product_name"],
		order_by="product_name asc",
		limit_page_length=0,
	)


def delete_document_setup(setup_id: str):
	_ensure_exists(setup_id)
	frappe.delete_doc(SETUP_DOCTYPE, setup_id, ignore_permissions=True)
