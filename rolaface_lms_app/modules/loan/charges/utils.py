import frappe
from typing import Dict, Any

def validate_charge_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        if not data.get("item_code") and not data.get("item_name"):
            raise frappe.ValidationError("Either 'item_code' or 'item_name' is required.")

    if data.get("item_group") and not frappe.db.exists("Item Group", data.get("item_group")):
        raise frappe.ValidationError(f"Item Group '{data.get('item_group')}' does not exist.")


def build_charge_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("item_group"):
        frappe_filters["item_group"] = args["item_group"]

    if args.get("disabled") is not None:
        frappe_filters["disabled"] = frappe.utils.cint(args.get("disabled"))

    return frappe_filters