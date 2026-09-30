# Copyright (c) 2026, Rolaface and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from rolaface_lms_app.modules.los.common import dump_json
from rolaface_lms_app.modules.los.document_setup.utils import validate_documents


class CustomLOSProductDocumentSetup(Document):
	def validate(self):
		self.documents = dump_json(validate_documents(self.documents))
