"""
Approve-and-email: an approval that is only done when its email reaches the investor.

  1. the approval is tried first and rolled back (it must be able to go through);
  2. the email is sent right away (Frappe sends it now and records it as a Communication + Email Queue);
     if it is not Sent, nothing is approved and the error is returned;
  3. the approval is done for real;
  4. the email is logged in Custom Investor Notification (shown in Investor 360 -> Notifications).

The email always goes to the investor's own email (Customer.email_id). The PDF is made by the screen and
uploaded first (file_id); the subject and message come from the screen as well.
"""
import frappe
from typing import Callable, Dict, Any

from .constant import DOCTYPE
from . import notifications


def _investor_email(investment: str) -> str:
    investor = frappe.db.get_value(DOCTYPE, investment, "investor")
    email = (frappe.db.get_value("Customer", investor, "email_id") or "").strip() if investor else ""
    if not email:
        raise frappe.ValidationError(
            "The investor has no email address. Add it to the customer, then approve again "
            "(nothing was approved)."
        )
    return email


def _mail_fields(mail: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in ("subject", "message", "file_id") if not (mail or {}).get(f)]
    if missing:
        raise frappe.ValidationError(f"Email {', '.join(missing)} missing: nothing was approved.")
    return mail


def _send_now(investment: str, to: str, mail: Dict[str, Any]) -> str:
    """Sends the email immediately; raises when it was not sent. Returns the Communication name."""
    from frappe.core.doctype.communication.email import make

    notifications._attach_file(mail["file_id"], investment)
    result = make(
        doctype=DOCTYPE,
        name=investment,
        content=mail.get("message_html") or mail["message"],
        subject=mail["subject"],
        recipients=to,
        send_email=True,
        attachments=[mail["file_id"]],
        send_me_a_copy=False,
        now=True,
    )
    communication = result.get("name") if isinstance(result, dict) else None
    queue = frappe.get_all(
        "Email Queue", filters={"communication": communication}, fields=["status", "error"]
    ) if communication else []
    if not queue or any(q.status != "Sent" for q in queue):
        error = next((q.error for q in queue if q.error), "") or ""
        reason = error.strip().splitlines()[-1] if error else "the mail server did not accept it"
        raise frappe.ValidationError(f"The email to {to} could not be sent ({reason}). Nothing was approved.")
    return communication


def approve_and_email(
    investment: str,
    approve: Callable[[], Dict[str, Any]],
    mail: Dict[str, Any],
    notification_type: str,
    reference: str,
    after_approve: Callable[[str, Dict[str, Any]], None] = None,
) -> Dict[str, Any]:
    mail = _mail_fields(mail)
    to = _investor_email(investment)

    # 1. The approval must be able to go through before anything is emailed.
    frappe.db.savepoint("approve_dry_run")
    try:
        approve()
    finally:
        frappe.db.rollback(save_point="approve_dry_run")

    # 2. Email now (this commits the Communication / Email Queue); stop here if it was not sent.
    _send_now(investment, to, mail)

    # 3. Approve for real, 4. log the notification.
    result = approve()
    if after_approve:
        after_approve(to, mail)
    notifications.log_notification({
        "investment": investment,
        "notification_type": notification_type,
        "sent_to": to,
        "subject": mail["subject"],
        "message": mail["message"],
        "file_id": mail["file_id"],
        "reference": reference,
    })
    return {**(result or {}), "emailed_to": to}
