# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

from frappe.contacts.address_and_contact import delete_contact_and_address, load_address_and_contact
from frappe.model.document import Document


class CustomLOSLoanApplication(Document):
	def onload(self):
		load_address_and_contact(self)

	def on_trash(self):
		delete_contact_and_address(self.doctype, self.name)
