# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CustomLOSProductAssignmentRule(Document):
	pass


def on_doctype_update():
	# Picking a product reads active rules in priority order.
	frappe.db.add_index("Custom LOS Product Assignment Rule", ["is_active", "priority"])
