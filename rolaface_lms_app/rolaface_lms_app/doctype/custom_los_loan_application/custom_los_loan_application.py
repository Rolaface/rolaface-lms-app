# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

from frappe.contacts.address_and_contact import delete_contact_and_address, load_address_and_contact
from frappe.model.document import Document

from rolaface_lms_app.modules.los.loan_application.constant import CLOSED_STATUSES


class CustomLOSLoanApplication(Document):
	def before_insert(self):
		self.custom_status = self.custom_status or "Draft"

	def validate(self):
		if not self.is_new() and self.has_value_changed("workflow_state"):
			self.custom_status = self.workflow_state if self.workflow_state in ("Draft", *CLOSED_STATUSES) else "Pending"

	def onload(self):
		load_address_and_contact(self)

	def on_trash(self):
		delete_contact_and_address(self.doctype, self.name)
