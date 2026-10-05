from typing import Any, Dict, List, Tuple

import frappe

from ..common import build_order_by, count_records, search_or_filters
from .constant import (
	ADDRESS_DOCTYPE,
	ADDRESS_FIELDS,
	ALLOWED_SORT_FIELDS,
	APPLICATION_DOCTYPE,
	ALLOWED_UPDATE_FIELDS,
	DRAFT,
	RETURN_FIELDS_GET_ALL,
	SEARCH_FIELDS,
)
from .utils import (
	add_display_names,
	build_application_filters,
	parse_application,
	set_application_values,
	set_stage_values,
	validate_addresses,
	validate_application,
	validate_create_payload,
	validate_update_payload,
)


def _ensure_exists(application_id: str) -> str:
	status = frappe.db.get_value(APPLICATION_DOCTYPE, application_id, "status")
	if not status:
		raise frappe.DoesNotExistError(f"Loan application '{application_id}' does not exist.")
	return status


def _ensure_draft(application_id: str, rule: str):
	status = _ensure_exists(application_id)
	if status != DRAFT:
		raise frappe.LinkExistsError(f"Loan application '{application_id}' is {status.lower()}; {rule}.")


def create_loan_application(data: Dict[str, Any]) -> Dict[str, Any]:
	validate_create_payload(data)
	addresses = validate_addresses(data.get("addresses"))

	application_doc = frappe.new_doc(APPLICATION_DOCTYPE)
	set_application_values(application_doc, data)
	validate_application(application_doc, [address["address_type"] for address in addresses])
	application_doc.insert(ignore_permissions=True)
	_insert_addresses(application_doc.name, addresses)
	return get_loan_application_by_id(application_doc.name)


def update_loan_application(application_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
	_ensure_exists(application_id)
	validate_update_payload(data)
	application_doc = frappe.get_doc(APPLICATION_DOCTYPE, application_id)

	if any(field in data for field in ALLOWED_UPDATE_FIELDS):
		_ensure_draft(application_id, "only a draft's application details can be edited")
		addresses = (
			validate_addresses(data["addresses"]) if "addresses" in data else _get_addresses(application_id)
		)
		set_application_values(application_doc, data)
		validate_application(application_doc, [address["address_type"] for address in addresses])

	set_stage_values(application_doc, data)
	application_doc.save(ignore_permissions=True)
	if "addresses" in data:
		_delete_addresses(application_id)
		_insert_addresses(application_id, addresses)
	return get_loan_application_by_id(application_id)


def get_loan_application_by_id(application_id: str) -> Dict[str, Any]:
	_ensure_exists(application_id)
	application = parse_application(frappe.get_doc(APPLICATION_DOCTYPE, application_id))
	application["addresses"] = _get_addresses(application_id)
	return add_display_names([application])[0]


def get_loan_applications(
	args: Dict[str, Any], page: int, page_size: int, sort_by: str, sort_order: str
) -> Tuple[List[Dict[str, Any]], int]:
	filters = build_application_filters(args)
	or_filters = search_or_filters(args.get("search"), SEARCH_FIELDS)
	order_by = build_order_by(APPLICATION_DOCTYPE, sort_by, sort_order, ALLOWED_SORT_FIELDS)

	applications = frappe.get_all(
		APPLICATION_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=RETURN_FIELDS_GET_ALL,
		order_by=order_by,
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	return add_display_names(applications), count_records(APPLICATION_DOCTYPE, filters, or_filters)


def delete_loan_application(application_id: str):
	_ensure_draft(application_id, "only a draft can be deleted")
	_delete_addresses(application_id)
	frappe.delete_doc(APPLICATION_DOCTYPE, application_id, ignore_permissions=True)


def _address_names(application_id: str) -> List[str]:
	return frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": ADDRESS_DOCTYPE,
			"link_doctype": APPLICATION_DOCTYPE,
			"link_name": application_id,
		},
		pluck="parent",
	)


def _get_addresses(application_id: str) -> List[Dict[str, Any]]:
	names = _address_names(application_id)
	if not names:
		return []
	return frappe.get_all(
		ADDRESS_DOCTYPE,
		filters={"name": ["in", names]},
		fields=["name", *ADDRESS_FIELDS],
		order_by="creation asc",
	)


def _insert_addresses(application_id: str, addresses: List[Dict[str, Any]]):
	for address in addresses:
		address_doc = frappe.new_doc(ADDRESS_DOCTYPE)
		address_doc.update({"address_title": application_id, **address})
		address_doc.append("links", {"link_doctype": APPLICATION_DOCTYPE, "link_name": application_id})
		address_doc.insert(ignore_permissions=True)


def _delete_addresses(application_id: str):
	for name in _address_names(application_id):
		address_doc = frappe.get_doc(ADDRESS_DOCTYPE, name)
		if len(address_doc.links) == 1:
			frappe.delete_doc(ADDRESS_DOCTYPE, name, ignore_permissions=True)
			continue
		address_doc.links = [
			link
			for link in address_doc.links
			if not (link.link_doctype == APPLICATION_DOCTYPE and link.link_name == application_id)
		]
		address_doc.save(ignore_permissions=True)
