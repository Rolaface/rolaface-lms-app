import json
from .party_utils import get_linked_terms, sync_terms
import frappe

def sync_company_terms(company_doc, terms_data) -> dict:
    if not terms_data:
        return {}

    if isinstance(terms_data, str):
        try:
            terms_data = json.loads(terms_data)
        except json.JSONDecodeError:
            raise frappe.ValidationError("Invalid JSON in 'terms'.")

    result = {}

    for terms_type, type_data in terms_data.items():
        if terms_type not in ["buying", "selling"]:
            continue

        tc_name = sync_terms(company_doc, {terms_type: type_data}, terms_type)
        result[f"{terms_type}_tc"] = tc_name

        if tc_name:
            tc_field = "default_selling_terms" if terms_type == "selling" else "default_buying_terms"
            if hasattr(company_doc, tc_field):
                company_doc.db_set(tc_field, tc_name, update_modified=False)
    return result

def get_company_terms(company) -> dict:
    result = {}

    for terms_type in ["selling", "buying"]:
        tc_field = f"default_{terms_type}_terms"
        tc_name = getattr(company, tc_field, None)

        if not tc_name:
            result[terms_type] = None
            continue
        try:
            result = {**result, **get_linked_terms(company.name, terms_type)}
        except Exception:
            result[terms_type] = None

    return result