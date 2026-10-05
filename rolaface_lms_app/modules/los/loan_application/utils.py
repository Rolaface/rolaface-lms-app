from typing import Any, Dict, List, Optional

import frappe
from frappe.model import no_value_fields
from frappe.utils import getdate, nowdate

from ..common import add_date_range, dump_json, load_json, name_map
from ..loan_type_tree.constant import (
	LEVEL_LOAN_TYPE,
	LEVEL_PURPOSE,
	LEVEL_SUB_TYPE,
	PARENT_FIELD,
	TREE_DOCTYPE,
)
from .constant import (
	ADDRESS_FIELDS,
	ADDRESS_TYPES,
	ALLOWED_UPDATE_FIELDS,
	APPLICATION_DOCTYPE,
	BUSINESS,
	BUSINESS_FIELDS,
	CHANNEL_DOCTYPE,
	COMMON_FIELDS,
	CUSTOMER_DOCTYPE,
	DATE_FIELDS,
	EXISTING_CUSTOMER,
	FILTER_FIELDS,
	FINANCIAL_KEYS,
	INDIVIDUAL,
	INDIVIDUAL_FIELDS,
	LOAN_PRODUCT_DOCTYPE,
	MAX_TEXT_LENGTH,
	REQUIRED_ADDRESS_TYPE,
	STAGE_DATE_FIELDS,
	STAGE_FIELDS,
	STAGE_JSON_FIELDS,
	STAGE_NUMBER_FIELDS,
	STAGE_SELECT_FIELDS,
	TABLE_FIELDS,
	VALUATION_NUMBER_FIELDS,
	VALUATION_SELECT_FIELDS,
)

APPLICANT_FIELDS = {INDIVIDUAL: INDIVIDUAL_FIELDS, BUSINESS: BUSINESS_FIELDS}


def validate_create_payload(data: Dict[str, Any]):
	_reject_fixed_fields(data, ALLOWED_UPDATE_FIELDS)


def validate_update_payload(data: Dict[str, Any]):
	_reject_fixed_fields(data, ALLOWED_UPDATE_FIELDS | STAGE_FIELDS)
	if not any(field in data for field in ALLOWED_UPDATE_FIELDS | STAGE_FIELDS):
		raise frappe.ValidationError("Nothing to update. Send at least one application or stage field.")


def _reject_fixed_fields(data: Dict[str, Any], allowed: set):
	meta = frappe.get_meta(APPLICATION_DOCTYPE)
	fixed = sorted(field for field in data if field not in allowed and (meta.has_field(field) or field in STAGE_FIELDS))
	if fixed:
		raise frappe.ValidationError(f"{', '.join(fixed)} cannot be sent here.")


def set_application_values(application_doc, data: Dict[str, Any]):
	for field in (*COMMON_FIELDS, *BUSINESS_FIELDS, *INDIVIDUAL_FIELDS):
		if field in data:
			application_doc.set(
				field, _clean_value(field, application_doc.meta.get_label(field), data[field])
			)
	if "financials" in data:
		application_doc.financials = dump_json(validate_financials(data["financials"]))
	for table in TABLE_FIELDS:
		if table in data:
			application_doc.set(table, _clean_rows(table, data[table]))

	if application_doc.applicant_type == INDIVIDUAL:
		application_doc.update({field: None for field in BUSINESS_FIELDS})
		application_doc.set("directors", [])
	elif application_doc.applicant_type == BUSINESS:
		application_doc.update({field: None for field in INDIVIDUAL_FIELDS})
	if application_doc.customer_type != EXISTING_CUSTOMER:
		application_doc.customer = None


def set_stage_values(application_doc, data: Dict[str, Any]):
	for field, rules in STAGE_NUMBER_FIELDS.items():
		if field in data:
			application_doc.set(field, _number(data[field], application_doc.meta.get_label(field), **rules))
	for field in STAGE_SELECT_FIELDS:
		if field in data:
			application_doc.set(field, _text(data[field]) or "")
	for field in STAGE_DATE_FIELDS:
		if field in data:
			application_doc.set(field, _date(data[field], application_doc.meta.get_label(field)))
	for field in STAGE_JSON_FIELDS:
		if field in data:
			application_doc.set(field, dump_json(_object(data[field], field)))
	if "collateral_valuations" in data:
		_set_valuations(application_doc, data["collateral_valuations"])


def _set_valuations(application_doc, value):
	rows = {row.name: row for row in application_doc.collaterals}
	for index, valuation in enumerate(_list_of_objects(value, "collateral_valuations"), start=1):
		row = rows.get(valuation.get("row_id"))
		if not row:
			raise frappe.ValidationError(
				f"collateral_valuations row {index}: row_id '{valuation.get('row_id')}' is not a collateral of this application."
			)
		label = f"collateral_valuations row {index}"
		for field in VALUATION_NUMBER_FIELDS:
			if field in valuation:
				row.set(field, _number(valuation[field], f"{label}: {field}", allow_zero=True))
		for field in VALUATION_SELECT_FIELDS:
			if field in valuation:
				row.set(field, _text(valuation[field]) or "")
		if "valuation_details" in valuation:
			row.valuation_details = dump_json(_object(valuation["valuation_details"], f"{label}: valuation_details"))


def validate_application(application_doc, address_types: List[str]):
	_check_required(application_doc)
	_check_lengths(application_doc)
	_check_dates(application_doc)
	_check_loan_tree(application_doc)
	_check_channel_and_customer(application_doc)
	_check_rows(application_doc)

	if application_doc.applicant_type == BUSINESS and not application_doc.directors:
		raise frappe.ValidationError("Business applications need at least one director.")
	required_type = REQUIRED_ADDRESS_TYPE[application_doc.applicant_type]
	if required_type not in address_types:
		raise frappe.ValidationError(
			f"{application_doc.applicant_type} applications need an address with address_type {required_type}."
		)


def validate_financials(value) -> Optional[Dict[str, List[Dict[str, Any]]]]:
	try:
		financials = load_json(value, None)
	except frappe.ValidationError:
		financials = []
	if financials is None:
		return None
	if not isinstance(financials, dict):
		raise frappe.ValidationError(f"financials must be an object with {', '.join(FINANCIAL_KEYS)} lists.")

	cleaned = {}
	for key in FINANCIAL_KEYS:
		cleaned[key] = []
		for item in _list_of_objects(financials.get(key), f"financials.{key}"):
			source = _text(item.get("source"))
			if not source:
				raise frappe.ValidationError(f"financials.{key}: every item needs a source.")
			amount = _number(
				item.get("monthly_amount"), f"financials.{key} '{source}' monthly_amount", allow_zero=True
			)
			cleaned[key].append({"source": source, "monthly_amount": amount or 0})
	return cleaned


def validate_addresses(value) -> List[Dict[str, Any]]:
	seen, cleaned = set(), []
	for address in _list_of_objects(value, "addresses"):
		address = {field: _text(address.get(field)) for field in ADDRESS_FIELDS}
		address_type = address["address_type"]
		if address_type not in ADDRESS_TYPES:
			raise frappe.ValidationError(f"address_type must be one of: {', '.join(ADDRESS_TYPES)}.")
		if address_type in seen:
			raise frappe.ValidationError(f"Only one {address_type} address is allowed.")
		missing = [field for field in ("address_line1", "city", "country") if not address[field]]
		if missing:
			raise frappe.ValidationError(f"{address_type} address: {', '.join(missing)} required.")
		too_long = [field for field, text in address.items() if text and len(text) > MAX_TEXT_LENGTH]
		if too_long:
			raise frappe.ValidationError(
				f"{address_type} address: {', '.join(too_long)} cannot be longer than {MAX_TEXT_LENGTH} characters."
			)
		seen.add(address_type)
		cleaned.append(address)
	return cleaned


def parse_application(application_doc) -> Dict[str, Any]:
	result = {"name": application_doc.name, **_values(application_doc)}
	for table in TABLE_FIELDS:
		result[table] = [{"row_id": row.name, **_values(row)} for row in application_doc.get(table)]
	result.update(
		{field: application_doc.get(field) for field in ("owner", "creation", "modified_by", "modified")}
	)
	return result


def add_display_names(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	tree_fields = ("loan_type", "loan_sub_type", "loan_purpose")
	tree_names = name_map(
		TREE_DOCTYPE, [row.get(field) for row in rows for field in tree_fields], "node_name"
	)
	product_names = name_map(LOAN_PRODUCT_DOCTYPE, [row.get("loan_product") for row in rows], "product_name")
	customer_names = name_map(CUSTOMER_DOCTYPE, [row.get("customer") for row in rows], "customer_name")

	for row in rows:
		if row.get("applicant_type") == BUSINESS:
			row["applicant_name"] = row.get("company_name")
		else:
			row["applicant_name"] = " ".join(
				filter(None, (row.get("first_name"), row.get("middle_name"), row.get("last_name")))
			)
		for field in tree_fields:
			if field in row:
				row[f"{field}_name"] = tree_names.get(row[field])
		row["product_name"] = product_names.get(row.get("loan_product"))
		row["customer_name"] = customer_names.get(row.get("customer"))
	return rows


def build_application_filters(args: Dict[str, Any]) -> Dict[str, Any]:
	filters = {field: args.get(field) for field in FILTER_FIELDS if args.get(field)}
	add_date_range(filters, args, "application_date")
	return filters


def _clean_value(field: str, label: str, value):
	if field in DATE_FIELDS:
		return _date(value, label)
	if field == "requested_amount":
		return _number(value, label)
	if field == "tenure_months":
		return _number(value, label, whole=True)
	if field == "experience_years":
		return _number(value, label, allow_zero=True)
	return _text(value)


def _clean_rows(table: str, value) -> List[Dict[str, Any]]:
	cleaned = []
	for index, row in enumerate(_list_of_objects(value, table), start=1):
		values = {field: _text(row.get(field)) for field in TABLE_FIELDS[table]}
		if table == "collaterals":
			values["estimated_value"] = _number(
				row.get("estimated_value"), f"collaterals row {index}: estimated_value"
			)
			values["ownership_date"] = _date(
				row.get("ownership_date"), f"collaterals row {index}: ownership_date"
			)
		cleaned.append(values)
	return cleaned


def _check_required(application_doc):
	applicant_type = application_doc.applicant_type
	if applicant_type and applicant_type not in APPLICANT_FIELDS:
		raise frappe.ValidationError(f"applicant_type must be one of: {', '.join(APPLICANT_FIELDS)}.")

	required = [df.fieldname for df in application_doc.meta.fields if df.reqd]
	required += APPLICANT_FIELDS.get(applicant_type, ())
	if application_doc.customer_type == EXISTING_CUSTOMER:
		required.append("customer")

	missing = [
		application_doc.meta.get_label(field)
		for field in required
		if application_doc.get(field) in (None, "")
	]
	if missing:
		raise frappe.ValidationError(f"Required: {', '.join(missing)}.")


def _check_lengths(doc, prefix: str = ""):
	for df in doc.meta.fields:
		value = doc.get(df.fieldname)
		max_length = df.length or MAX_TEXT_LENGTH
		if df.fieldtype in ("Data", "Link", "Select") and isinstance(value, str) and len(value) > max_length:
			raise frappe.ValidationError(f"{prefix}{df.label} cannot be longer than {max_length} characters.")


def _check_dates(application_doc):
	today = getdate(nowdate())
	for field in DATE_FIELDS:
		if application_doc.get(field) and getdate(application_doc.get(field)) > today:
			raise frappe.ValidationError(f"{application_doc.meta.get_label(field)} cannot be in the future.")


def _check_loan_tree(application_doc):
	levels = (
		("loan_type", LEVEL_LOAN_TYPE, None),
		("loan_sub_type", LEVEL_SUB_TYPE, "loan_type"),
		("loan_purpose", LEVEL_PURPOSE, "loan_sub_type"),
	)
	nodes = {
		node.name: node
		for node in frappe.get_all(
			TREE_DOCTYPE,
			filters={"name": ["in", [application_doc.get(field) for field, _, _ in levels]]},
			fields=[
				"name",
				"node_name",
				"level",
				"applicant_type",
				"is_active",
				f"{PARENT_FIELD} as parent_node",
			],
		)
	}
	for field, level, parent_field in levels:
		label = application_doc.meta.get_label(field)
		node = nodes.get(application_doc.get(field))
		if not node or node.level != level:
			raise frappe.ValidationError(f"{label} '{application_doc.get(field)}' does not exist.")
		if parent_field and node.parent_node != application_doc.get(parent_field):
			parent = nodes[application_doc.get(parent_field)]
			raise frappe.ValidationError(
				f"{label} '{node.node_name}' does not belong to {application_doc.meta.get_label(parent_field)} '{parent.node_name}'."
			)
		if not node.is_active:
			raise frappe.ValidationError(f"{label} '{node.node_name}' is inactive.")
		if level == LEVEL_LOAN_TYPE and node.applicant_type != application_doc.applicant_type:
			raise frappe.ValidationError(
				f"Loan Type '{node.node_name}' is for {node.applicant_type} applicants."
			)


def _check_channel_and_customer(application_doc):
	if not frappe.db.get_value(CHANNEL_DOCTYPE, application_doc.channel, "is_active"):
		raise frappe.ValidationError(f"Channel '{application_doc.channel}' does not exist or is inactive.")
	if application_doc.customer:
		disabled = frappe.db.get_value(CUSTOMER_DOCTYPE, application_doc.customer, "disabled")
		if disabled is None:
			raise frappe.ValidationError(f"Customer '{application_doc.customer}' does not exist.")
		if disabled:
			raise frappe.ValidationError(f"Customer '{application_doc.customer}' is disabled.")


def _check_rows(application_doc):
	for table in TABLE_FIELDS:
		for index, row in enumerate(application_doc.get(table), start=1):
			missing = [df.label for df in row.meta.fields if df.reqd and row.get(df.fieldname) in (None, "")]
			if missing:
				raise frappe.ValidationError(f"{table} row {index}: {', '.join(missing)} required.")
			_check_lengths(row, f"{table} row {index}: ")


def _values(doc) -> Dict[str, Any]:
	values = {}
	for df in doc.meta.fields:
		if df.fieldtype not in no_value_fields:
			value = doc.get(df.fieldname)
			values[df.fieldname] = load_json(value, None) if df.fieldtype == "JSON" else value
	return values


def _object(value, label: str) -> Optional[Dict[str, Any]]:
	try:
		value = load_json(value, None)
	except frappe.ValidationError:
		value = []
	if value is not None and not isinstance(value, dict):
		raise frappe.ValidationError(f"{label} must be an object.")
	return value


def _list_of_objects(value, label: str) -> List[Dict[str, Any]]:
	try:
		rows = load_json(value, [])
	except frappe.ValidationError:
		rows = None
	if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
		raise frappe.ValidationError(f"{label} must be a list of objects.")
	return rows


def _text(value) -> Optional[str]:
	if value is None:
		return None
	value = str(value).strip()
	return value or None


def _date(value, label: str) -> Optional[str]:
	if value is None or str(value).strip() == "":
		return None
	try:
		return getdate(value).isoformat()
	except Exception:
		raise frappe.ValidationError(f"{label} must be a date (YYYY-MM-DD).")


def _number(value, label: str, whole: bool = False, allow_zero: bool = False):
	if value is None or str(value).strip() == "":
		return None
	try:
		number = float(value)
	except (TypeError, ValueError):
		raise frappe.ValidationError(f"{label} must be a number.")
	if whole and not number.is_integer():
		raise frappe.ValidationError(f"{label} must be a whole number.")
	if number < 0 or (number == 0 and not allow_zero):
		raise frappe.ValidationError(f"{label} must be {'0 or more' if allow_zero else 'more than 0'}.")
	return int(number) if whole else number
