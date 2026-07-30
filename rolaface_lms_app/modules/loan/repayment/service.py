import frappe
from typing import Tuple, Dict, Any
from .constant import ALLOWED_PAYMENT_FIELD

def create_payment(data: Dict[str, Any]):
    payment_doc = frappe.new_doc("Loan Repayment")
    for field in ALLOWED_PAYMENT_FIELD:
        if field in data and data.get(field) is not None:
            payment_doc.set(field, data.get(field))
    payment_doc.insert(ignore_permissions=True)
    
    