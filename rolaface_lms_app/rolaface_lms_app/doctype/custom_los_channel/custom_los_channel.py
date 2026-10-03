# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from rolaface_lms_app.modules.los.channel.service import replace_channel_in_rules


class CustomLOSChannel(Document):
	def after_rename(self, old, new, merge):
		replace_channel_in_rules(old, new)
