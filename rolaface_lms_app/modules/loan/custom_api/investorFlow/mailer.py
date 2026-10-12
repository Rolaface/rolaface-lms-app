"""
Approve, then email: the approval is saved first; the email is sent right after it.

  1. the approval is done and committed;
  2. the email is sent right away (Frappe sends it now and records it as a Communication + Email Queue);
  3. when it was sent: it is logged in Custom Investor Notification (Investor 360 -> Notifications) and
     after_email runs (e.g. the contract is marked Sent);
     when it was not sent: the approval stays, the result carries "email_error", and the user sends it
     again with Compose Mail. An unsent email is set to Error in Email Queue, so it does not go out later
     on its own as well.

The email goes to the investor's own email (Customer.email_id). The PDF is made by the screen and
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
        raise frappe.ValidationError("the investor has no email address; add it to the customer first")
    return email


def _mail_fields(mail: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in ("subject", "message", "file_id") if not (mail or {}).get(f)]
    if missing:
        raise frappe.ValidationError(f"email {', '.join(missing)} missing")
    return mail


def _send_now(investment: str, to: str, mail: Dict[str, Any]) -> str:
    """Queues the email, then sends it right here; raises when it was not sent. Returns the Communication name.

    make(now=True) would only send it after the request commits (frappe.db.after_commit), too late to tell the
    screen, so it is queued (now=False) and its Email Queue sent directly. A failed email is set to Error so the
    scheduler does not send it again later on its own (the user sends it with Compose Mail instead).
    """
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
        now=False,
    )
    communication = result.get("name") if isinstance(result, dict) else None
    queues = frappe.get_all("Email Queue", filters={"communication": communication}, pluck="name") if communication else []
    if not queues:
        raise frappe.ValidationError(f"the email to {to} could not be queued")

    reason = ""
    for name in queues:
        queue = frappe.get_doc("Email Queue", name)
        if not queue.can_send_now():
            reason = "email sending is muted or the email queue is suspended"
            break
        try:
            queue.send()  # commits its own status (Sending -> Sent / Not Sent)
        except Exception as e:
            reason = str(e)
            break
        status, error = frappe.db.get_value("Email Queue", name, ["status", "error"])
        if status != "Sent":
            reason = (error or "").strip().splitlines()[-1] if error else "the mail server did not accept it"
            break

    if reason:
        for name in queues:
            if frappe.db.get_value("Email Queue", name, "status") != "Sent":
                frappe.db.set_value("Email Queue", name, "status", "Error")
        frappe.db.commit()
        raise frappe.ValidationError(f"the email to {to} could not be sent ({reason})")
    return communication


def approve_and_email(
    investment: str,
    approve: Callable[[], Dict[str, Any]],
    mail: Dict[str, Any],
    notification_type: str,
    reference: str,
    after_email: Callable[[str, Dict[str, Any]], None] = None,
) -> Dict[str, Any]:
    # 1. Approve and keep it, whatever happens to the email.
    result = approve() or {}
    frappe.db.commit()

    # 2. Email; 3. log it, or report why it was not sent.
    to = None
    try:
        mail = _mail_fields(mail)
        to = _investor_email(investment)
        _send_now(investment, to, mail)
        if after_email:
            after_email(to, mail)
        notifications.log_notification({
            "investment": investment,
            "notification_type": notification_type,
            "sent_to": to,
            "subject": mail["subject"],
            "message": mail["message"],
            "file_id": mail["file_id"],
            "reference": reference,
        })
        frappe.db.commit()
        return {**result, "emailed_to": to}
    except Exception as e:
        # The approval is already committed; anything left uncommitted from the email is dropped.
        frappe.db.rollback()
        frappe.log_error(title=f"Investor approval email not sent: {investment}")
        return {**result, "email_error": str(e), "email_to": to}
