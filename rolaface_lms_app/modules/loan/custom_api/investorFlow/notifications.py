"""
Investor notifications: every email sent to an investor, logged in Custom Investor Notification.

  Contract           - the investment / renewal contract
  Investment         - fund receipt statement (sent when a fund record is approved)
  Payment Statement  - payout statement (sent when a schedule row is paid)

The email itself is sent by the screen (frappe.core.doctype.communication.email.make, with the PDF attached);
log_notification records it here, attaches the PDF to the investment and links the Communication.
"""
import frappe
from typing import Dict, Any, List, Optional
from frappe.utils import now_datetime, validate_email_address

from .constant import DOCTYPE

NOTIFICATION_DOCTYPE = "Custom Investor Notification"
NOTIFICATION_TYPES = ["Contract", "Investment", "Payment Statement"]

LIST_FIELDS = [
    "name", "investor", "investment", "notification_type", "sent_to", "subject", "message",
    "file", "reference", "communication", "sent_on",
]


def _attach_file(file_id: str, investment: str) -> Dict[str, Any]:
    """The emailed PDF is attached to the investment (unless it already is)."""
    file_doc = frappe.db.get_value(
        "File", file_id, ["name", "file_url", "file_name", "attached_to_doctype", "attached_to_name"], as_dict=True
    )
    if not file_doc:
        raise frappe.DoesNotExistError(f"File '{file_id}' does not exist.")
    here = file_doc.attached_to_doctype == DOCTYPE and file_doc.attached_to_name == investment
    if file_doc.attached_to_doctype and not here:
        raise frappe.ValidationError(f"File '{file_id}' is already attached to another document.")
    if not here:
        frappe.db.set_value("File", file_id, {"attached_to_doctype": DOCTYPE, "attached_to_name": investment})
    return file_doc


def _find_communication(investment: str, subject: str) -> Optional[str]:
    """The email Frappe recorded for this send: latest Communication on the investment with this subject."""
    rows = frappe.get_all(
        "Communication",
        filters={"reference_doctype": DOCTYPE, "reference_name": investment, "subject": subject},
        pluck="name",
        order_by="creation desc",
        limit=1,
    )
    return rows[0] if rows else None


def log_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in ("investment", "notification_type", "sent_to", "subject", "file_id") if not data.get(f)]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")
    if data.get("notification_type") not in NOTIFICATION_TYPES:
        raise frappe.ValidationError(f"Notification Type must be one of: {', '.join(NOTIFICATION_TYPES)}.")

    investment = data.get("investment")
    investor = frappe.db.get_value(DOCTYPE, investment, "investor")
    if not investor:
        raise frappe.DoesNotExistError(f"Investor Flow '{investment}' does not exist.")
    sent_to = str(data.get("sent_to")).strip()
    validate_email_address(sent_to, throw=True)

    file_doc = _attach_file(data.get("file_id"), investment)
    doc = frappe.get_doc({
        "doctype": NOTIFICATION_DOCTYPE,
        "investor": investor,
        "investment": investment,
        "notification_type": data.get("notification_type"),
        "sent_to": sent_to,
        "subject": data.get("subject"),
        "message": data.get("message"),
        "file": file_doc.name,
        "reference": data.get("reference"),
        "communication": _find_communication(investment, data.get("subject")),
        "sent_on": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return _row(doc.as_dict(), {file_doc.name: file_doc})


def _row(row, files: Dict[str, Any]) -> Dict[str, Any]:
    file_doc = files.get(row.get("file")) or {}
    return {
        **{f: row.get(f) for f in LIST_FIELDS},
        "file_url": file_doc.get("file_url"),
        "file_name": file_doc.get("file_name"),
    }


def get_investor_notifications(investor: str, notification_type: Optional[str] = None,
                               investment: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every notification sent to the investor, newest first."""
    if not investor:
        raise frappe.ValidationError("investor is required.")
    filters = {"investor": investor}
    if notification_type:
        filters["notification_type"] = notification_type
    if investment:
        filters["investment"] = investment
    rows = frappe.get_all(NOTIFICATION_DOCTYPE, filters=filters, fields=LIST_FIELDS, order_by="sent_on desc")
    file_ids = [r.file for r in rows if r.file]
    files = {
        f.name: f
        for f in frappe.get_all(
            "File", filters={"name": ["in", file_ids]}, fields=["name", "file_url", "file_name"]
        )
    } if file_ids else {}
    return [_row(r, files) for r in rows]
