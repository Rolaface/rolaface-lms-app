import json
import re
import frappe
from typing import Dict, List, Any

def parse_api_payload() -> Dict[str, Any]:
    data = frappe.local.form_dict.copy()
    if hasattr(frappe.request, 'data') and frappe.request.data:
        try:
            raw_data = frappe.request.data
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            if raw_data.strip():
                parsed_json = json.loads(raw_data)
                if isinstance(parsed_json, dict):
                    data.update(parsed_json)
        except json.JSONDecodeError as e:
            raise frappe.ValidationError(f"Invalid JSON payload provided: {str(e)}")
    return data