// Copyright (c) 2026, Rolaface and contributors
// For license information, please see license.txt

frappe.ui.form.on("Custom LOS Loan Application", {
	refresh(frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: "name", doctype: frm.doctype };
		if (frm.is_new()) {
			frappe.contacts.clear_address_and_contact(frm);
		} else {
			frappe.contacts.render_address_and_contact(frm);
		}
	},
});
