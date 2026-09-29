# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomLOSLoanTypeTree(Document):
	pass


def on_doctype_update():
	# Lookups filter by applicant type and level (loan types) and sort by name.
	frappe.db.add_index("Custom LOS Loan Type Tree", ["applicant_type", "level", "is_active"])
