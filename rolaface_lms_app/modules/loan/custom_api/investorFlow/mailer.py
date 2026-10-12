"""
Approve, then email in the background: the approval request returns as soon as the approval is saved.

  1. the approval is done and committed; the request returns;
  2. a background job (queue "short") sends the email (queued as a Communication + Email Queue and sent there);
  3. when it was sent: it is logged in Custom Investor Notification (Investor 360 -> Notifications) and
     after_email runs (e.g. the contract is marked Sent);
     when it was not sent: it is recorded in the Error Log and its Email Queue set to Error (so it does not go
     out later on its own as well); the user sends it with Compose Mail.

The email goes to the investor's own email (Customer.email_id). The PDF is made by the screen and
uploaded first (file_id); the subject and message come from the screen as well.
Compose Mail does not use this module.
"""
import frappe
from typing import Callable, Dict, Any, Optional

from .constant import DOCTYPE, CONTRACT_STATUS_SENT
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


def _save_contract_fields(investment: str, to: str, mail: Dict[str, Any]):
    """The contract was emailed: save To / Subject / Message and set Contract Status to Sent."""
    frappe.db.set_value(DOCTYPE, investment, {
        "mail_sent": to,
        "subject": mail["subject"],
        "message": mail["message"],
        "contract_status": CONTRACT_STATUS_SENT,
    })


# What runs after the email was sent (a name, as the background job cannot take a function).
AFTER_EMAIL = {"contract": _save_contract_fields}


def approve_and_email(
    investment: str,
    approve: Callable[[], Dict[str, Any]],
    mail: Dict[str, Any],
    notification_type: str,
    reference: str,
    after_email: Optional[str] = None,
) -> Dict[str, Any]:
    # 1. Approve and keep it.
    result = approve() or {}
    frappe.db.commit()

    # 2. The email is sent in the background; the approval does not wait for it.
    frappe.enqueue(
        "rolaface_lms_app.modules.loan.custom_api.investorFlow.mailer.send_approval_email",
        queue="short",
        investment=investment,
        mail={k: v for k, v in (mail or {}).items() if k in ("subject", "message", "message_html", "file_id")},
        notification_type=notification_type,
        reference=reference,
        after_email=after_email,
    )
    return result


def send_approval_email(
    investment: str,
    mail: Dict[str, Any],
    notification_type: str,
    reference: str,
    after_email: Optional[str] = None,
):
    """Background job: sends the approval email; 3. logs it, or records why it was not sent."""
    try:
        mail = _mail_fields(mail)
        to = _investor_email(investment)
        _send_now(investment, to, mail)
        if after_email in AFTER_EMAIL:
            AFTER_EMAIL[after_email](investment, to, mail)
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
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title=f"Investor approval email not sent: {investment}")
        frappe.db.commit()
