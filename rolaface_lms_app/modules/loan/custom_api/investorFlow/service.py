import frappe
from typing import Tuple, Dict, Any
from .constant import (
    DOCTYPE,
    ALLOWED_INVESTOR_FLOW_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
    DEFAULT_STATUS,
    DELETABLE_STATUSES,
    FUND_STATUS_PENDING,
    FUND_STATUS_PARTIAL,
    FUND_STATUS_PAID,
    FUND_LIST_STATUSES,
    FUND_TABLE_FIELD,
    FUND_RECORD_DOCTYPE,
    RECORD_STATUS_DRAFT,
    RECORD_STATUS_APPROVED,
    RECORD_STATUS_CANCELLED,
    STATUS_APPROVED,
    STATUS_PAID,
    STATUS_ACTION_MAP,
    ALLOWED_STATUS_TRANSITIONS,
    CONTRACT_STATUS_PENDING,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_PAID,
    RETURN_FIELDS_BANK_ACCOUNT,
    STATUS_RECEIVED,
    REPAYMENT_FREQUENCIES,
    SCHEDULE_TABLE_FIELD,
    EARNING_DETAIL_FIELDS,
    EARNING_SCHEDULE_ROW_FIELDS,
    EARNING_AMOUNT_FIELDS,
    RETURN_FIELDS_EARNINGS_LIST,
    EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS,
    EARNING_FUND_STATUSES,
    CONTRACT_TERM_FIELDS,
    STATUS_MATURED,
    ROW_STATUS_PENDING,
    ROW_STATUS_ACCRUED,
    ROW_STATUS_PAID,
)
from . import accounting
from .utils import (
    _validate_investor_flow_payload,
    _build_investor_flow_filters,
    _as_list,
    _parse_date,
    current_schedule,
    schedule_history,
    schedule_version,
)
from frappe.utils import getdate, add_months, add_days, flt, nowdate, cint, validate_email_address


def create_investor_flow(data: Dict[str, Any]) -> Dict[str, Any]:
    _validate_investor_flow_payload(data, is_update=False)

    investor_flow_doc = frappe.new_doc(DOCTYPE)

    for field in ALLOWED_INVESTOR_FLOW_FIELDS:
        if field in data and data.get(field) is not None:
            investor_flow_doc.set(field, data.get(field))

    investor_flow_doc.status = DEFAULT_STATUS
    investor_flow_doc.fund_status = FUND_STATUS_PENDING
    investor_flow_doc.insert(ignore_permissions=True)
    return get_investor_flow_by_id(investor_flow_doc.name)


def update_investor_flow(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")

    investor_flow_doc = frappe.get_doc(DOCTYPE, investor_flow_id)

    _validate_investor_flow_payload(data, is_update=True, existing_doc=investor_flow_doc)

    # A renewed investment's amount is the principal carried over; it cannot change.
    if (
        investor_flow_doc.get("renewed_from")
        and data.get("investment_amount") is not None
        and flt(data.get("investment_amount")) != flt(investor_flow_doc.investment_amount)
    ):
        raise frappe.ValidationError(
            f"Investment Amount is the principal renewed from '{investor_flow_doc.renewed_from}' "
            f"({investor_flow_doc.investment_amount}) and cannot be changed."
        )
    has_changes = False

    for field in ALLOWED_INVESTOR_FLOW_FIELDS:
        if field in data and data.get(field) is not None:
            # str() so a stored date/number and the same value sent as text count as equal
            if str(investor_flow_doc.get(field)) != str(data.get(field)):
                investor_flow_doc.set(field, data.get(field))
                has_changes = True

    if has_changes:
        investor_flow_doc.save(ignore_permissions=True)

    return get_investor_flow_by_id(investor_flow_doc.name)


def get_investor_flow_by_id(investor_flow_id: str) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")

    investor_flow_doc = frappe.get_doc(DOCTYPE, investor_flow_id)
    result = {field: investor_flow_doc.get(field) for field in RETURN_FIELDS_GET_BY_ID}

    return result


def get_investor_flows(
    args: Dict[str, Any], page: int, page_size: int, sort_by="creation", sort_order="desc"
) -> Tuple[list, int, int]:
    start = (page - 1) * page_size
    or_filters = []

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        or_filters = [
            ["name", "like", search_term],
            ["investor", "like", search_term],
            ["investment_product", "like", search_term],
        ]

    safe_filters = _build_investor_flow_filters(args)

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise frappe.ValidationError(f"Invalid sort_by field: {sort_by}")

    sort_order_clean = str(sort_order).lower()
    if sort_order_clean not in ["asc", "desc"]:
        raise frappe.ValidationError("Invalid sort_order value. Use 'asc' or 'desc'.")

    order_by_string = f"`tab{DOCTYPE}`.`{sort_by}` {sort_order_clean}"

    investor_flows = frappe.get_all(
        DOCTYPE,
        filters=safe_filters,
        or_filters=or_filters if search else None,
        fields=RETURN_FIELDS_GET_ALL,
        limit_start=start,
        limit_page_length=page_size,
        order_by=order_by_string,
    )

    # Send the customer's name as "investor" and keep the ID in "investor_id".
    investor_ids = list({row.investor for row in investor_flows if row.investor})
    investor_names = dict(
        frappe.get_all(
            "Customer",
            filters={"name": ["in", investor_ids]},
            fields=["name", "customer_name"],
            as_list=True,
        )
    ) if investor_ids else {}

    for row in investor_flows:
        row["investor_id"] = row.investor
        row["investor"] = investor_names.get(row.investor) or row.investor

    total_records = len(
        frappe.get_all(
            DOCTYPE,
            filters=safe_filters,
            or_filters=or_filters if search else None,
            pluck="name",
        )
    )

    total_pages = (total_records + page_size - 1) // page_size

    return investor_flows, total_records, total_pages


def delete_investor_flow(investor_flow_id: str):
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")

    status, renewed_from = frappe.db.get_value(DOCTYPE, investor_flow_id, ["status", "renewed_from"])
    if (status or DEFAULT_STATUS) not in DELETABLE_STATUSES:
        raise frappe.ValidationError(
            f"Only {' or '.join(DELETABLE_STATUSES)} investments can be deleted (current status: '{status}')."
        )
    if renewed_from:
        raise frappe.ValidationError(
            f"Investor Flow '{investor_flow_id}' carries the principal renewed from '{renewed_from}' "
            "and cannot be deleted."
        )

    frappe.delete_doc(DOCTYPE, investor_flow_id, ignore_permissions=True)

def update_investor_flow_status(investor_flow_id: str, action: str) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")

    if action not in STATUS_ACTION_MAP:
        raise frappe.ValidationError(
            f"Invalid action. Allowed: {', '.join(STATUS_ACTION_MAP)}"
        )

    investor_flow_doc = frappe.get_doc(DOCTYPE, investor_flow_id)
    current_status = investor_flow_doc.status or DEFAULT_STATUS
    new_status = STATUS_ACTION_MAP[action]

    if new_status not in ALLOWED_STATUS_TRANSITIONS.get(current_status, []):
        raise frappe.ValidationError(
            f"Cannot change Investor Flow status from '{current_status}' to '{new_status}'."
        )

    if new_status == "Cancelled" and investor_flow_doc.get("renewed_from"):
        raise frappe.ValidationError(
            f"Investor Flow '{investor_flow_doc.name}' carries the principal renewed from "
            f"'{investor_flow_doc.renewed_from}' and cannot be cancelled."
        )

    investor_flow_doc.status = new_status
    investor_flow_doc.save(ignore_permissions=True)

    return {
        "id": investor_flow_doc.name,
        "previous_status": current_status,
        "status": investor_flow_doc.status,
    }


def _get_existing_investor_flow(investor_flow_id: str):
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")
    return frappe.get_doc(DOCTYPE, investor_flow_id)


def get_investor_bank_accounts(investor: str) -> list:
    """Enabled Bank Accounts whose Party is the investor (Customer)."""
    if not frappe.db.exists("Customer", investor):
        raise frappe.DoesNotExistError(f"Investor (Customer) '{investor}' does not exist.")

    bank_accounts = frappe.get_all(
        "Bank Account",
        filters={"party_type": "Customer", "party": investor, "disabled": 0},
        fields=RETURN_FIELDS_BANK_ACCOUNT,
        order_by="is_default desc, creation desc",
    )

    gl_accounts = [ba.account for ba in bank_accounts if ba.account]
    currency_map = dict(
        frappe.get_all(
            "Account",
            filters={"name": ["in", gl_accounts]},
            fields=["name", "account_currency"],
            as_list=True,
        )
    ) if gl_accounts else {}

    for ba in bank_accounts:
        ba["account_currency"] = currency_map.get(ba.account)

    return bank_accounts


def save_contract(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves the contract that was emailed (frappe.core.doctype.communication.email.make):
    To, Subject, the contract File attached to this Investor Flow, and Contract Status = Sent.
    """
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)

    if investor_flow_doc.contract_status == CONTRACT_STATUS_PAID:
        raise frappe.ValidationError("Contract is already Paid. It cannot be changed.")

    missing = [f for f in ("to", "subject", "message", "file_id") if not data.get(f)]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    to = str(data.get("to")).strip()
    validate_email_address(to, throw=True)

    file_id = data.get("file_id")
    file_doc = frappe.db.get_value(
        "File", file_id, ["name", "file_url", "attached_to_doctype", "attached_to_name"], as_dict=True
    )
    if not file_doc:
        raise frappe.DoesNotExistError(f"File '{file_id}' does not exist.")

    already_here = (
        file_doc.attached_to_doctype == DOCTYPE and file_doc.attached_to_name == investor_flow_doc.name
    )
    if file_doc.attached_to_doctype and not already_here:
        raise frappe.ValidationError(f"File '{file_id}' is already attached to another document.")

    if not already_here:
        frappe.db.set_value(
            "File", file_id, {"attached_to_doctype": DOCTYPE, "attached_to_name": investor_flow_doc.name}
        )

    investor_flow_doc.mail_sent = to
    investor_flow_doc.subject = data.get("subject")
    investor_flow_doc.message = data.get("message")
    investor_flow_doc.contract_status = CONTRACT_STATUS_SENT
    investor_flow_doc.save(ignore_permissions=True)

    return {
        "id": investor_flow_doc.name,
        "contract_status": investor_flow_doc.contract_status,
        "mail_sent": investor_flow_doc.mail_sent,
        "subject": investor_flow_doc.subject,
        "message": investor_flow_doc.message,
        "file_id": file_doc.name,
        "file_url": file_doc.file_url,
    }


FUND_INPUT_FIELDS = ["paid_date", "mode_of_payment", "reference_number", "amount"]

FUND_RECORD_FIELDS = [
    "name", "parent", "idx", "investor_id", "amount_paid", "mode_of_payment", "reference_number",
    "debit_gl", "debit_gl_description", "credit_gl", "credit_gl_description", "paid_date",
    "record_status", "journal_entry",
]


def _fund_rows(investor_flow_doc) -> list:
    return list(investor_flow_doc.get(FUND_TABLE_FIELD) or [])


def _sum_amount(rows, statuses) -> float:
    return flt(sum(flt(r.amount_paid) for r in rows if (r.get("record_status") or RECORD_STATUS_DRAFT) in statuses), 2)


def _fund_summary(investment_amount, rows, fund_status) -> Dict[str, Any]:
    """Fund received = Approved records; Draft records reserve their amount until approved or cancelled."""
    investment_amount = flt(investment_amount, 2)
    received = _sum_amount(rows, (RECORD_STATUS_APPROVED,))
    drafts = _sum_amount(rows, (RECORD_STATUS_DRAFT,))
    approved = [r for r in rows if r.get("record_status") == RECORD_STATUS_APPROVED]
    latest = max(approved, key=lambda r: (getdate(r.paid_date), r.idx)) if approved else None
    return {
        "investment_amount": investment_amount,
        "fund_received": received,
        "remaining_fund": max(flt(investment_amount - received, 2), 0),
        "draft_amount": drafts,
        # What can still be added as a new record (drafts included).
        "available_to_record": max(flt(investment_amount - received - drafts, 2), 0),
        "fund_status": fund_status or FUND_STATUS_PENDING,
        "last_paid_date": latest.paid_date if latest else None,
        "last_mode_of_payment": latest.mode_of_payment if latest else None,
    }


def _refresh_fund_status(investor_flow_doc):
    """Fund Status from the Approved records; Status Paid when the full amount is approved."""
    received = _sum_amount(_fund_rows(investor_flow_doc), (RECORD_STATUS_APPROVED,))
    investment_amount = flt(investor_flow_doc.investment_amount, 2)
    if received <= 0:
        investor_flow_doc.fund_status = FUND_STATUS_PENDING
    elif received < investment_amount:
        investor_flow_doc.fund_status = FUND_STATUS_PARTIAL
    else:
        investor_flow_doc.fund_status = FUND_STATUS_PAID

    if investor_flow_doc.fund_status == FUND_STATUS_PAID:
        investor_flow_doc.status = STATUS_PAID
    elif investor_flow_doc.status == STATUS_PAID:
        investor_flow_doc.status = STATUS_APPROVED


def _get_fund_record(investor_flow_doc, record_name: str):
    row = next((r for r in _fund_rows(investor_flow_doc) if r.name == record_name), None)
    if not row:
        raise frappe.DoesNotExistError(
            f"Fund record '{record_name}' does not belong to Investor Flow '{investor_flow_doc.name}'."
        )
    return row


def _validate_fund_input(investor_flow_doc, data: Dict[str, Any], current_row=None) -> Dict[str, Any]:
    missing = [f for f in FUND_INPUT_FIELDS if data.get(f) in (None, "")]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    try:
        amount = flt(data.get("amount"), 2)
    except (TypeError, ValueError):
        raise frappe.ValidationError("Amount must be a number.")
    if amount <= 0:
        raise frappe.ValidationError("Amount must be greater than 0.")

    others = [r for r in _fund_rows(investor_flow_doc) if current_row is None or r.name != current_row.name]
    available = flt(
        flt(investor_flow_doc.investment_amount, 2)
        - _sum_amount(others, (RECORD_STATUS_APPROVED, RECORD_STATUS_DRAFT)),
        2,
    )
    if amount > available:
        raise frappe.ValidationError(
            f"Amount cannot be more than {available}: the investment amount minus the approved and draft records."
        )

    # Paid to = the GL set for the Mode of Payment, Paid from = Investor Creditor GL (Investor Settings).
    fund_accounts = accounting.get_fund_accounts(data.get("mode_of_payment"))
    return {
        "amount_paid": amount,
        "mode_of_payment": data.get("mode_of_payment"),
        "reference_number": data.get("reference_number"),
        "paid_date": _parse_date(data.get("paid_date"), "Paid Date"),
        "debit_gl": fund_accounts["debit_gl"],
        "debit_gl_description": fund_accounts["debit_gl_description"],
        "credit_gl": fund_accounts["credit_gl"],
        "credit_gl_description": fund_accounts["credit_gl_description"],
    }


def _record_dict(investor_flow_doc, row) -> Dict[str, Any]:
    return {
        **{f: row.get(f) for f in FUND_RECORD_FIELDS if f != "parent"},
        "investment_id": investor_flow_doc.name,
        "record_status": row.get("record_status") or RECORD_STATUS_DRAFT,
    }


def add_fund_record(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves a fund received from the investor as a Draft record (no accounting until it is approved)."""
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    if investor_flow_doc.status != STATUS_APPROVED:
        raise frappe.ValidationError(
            f"Funds can be recorded only for an Approved investment (current status: '{investor_flow_doc.status}')."
        )

    values = _validate_fund_input(investor_flow_doc, data)
    row = investor_flow_doc.append(FUND_TABLE_FIELD, {
        **values,
        "investor_id": investor_flow_doc.investor,
        "investment_id": investor_flow_doc.name,
        "record_status": RECORD_STATUS_DRAFT,
    })
    investor_flow_doc.save(ignore_permissions=True)
    return _record_dict(investor_flow_doc, row)


def update_fund_record(investor_flow_id: str, record_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    row = _get_fund_record(investor_flow_doc, record_name)
    if (row.get("record_status") or RECORD_STATUS_DRAFT) != RECORD_STATUS_DRAFT:
        raise frappe.ValidationError(f"Only a Draft fund record can be edited (this one is {row.record_status}).")

    for field, value in _validate_fund_input(investor_flow_doc, data, current_row=row).items():
        row.set(field, value)
    investor_flow_doc.save(ignore_permissions=True)
    return _record_dict(investor_flow_doc, row)


def delete_fund_record(investor_flow_id: str, record_name: str):
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    row = _get_fund_record(investor_flow_doc, record_name)
    if (row.get("record_status") or RECORD_STATUS_DRAFT) not in (RECORD_STATUS_DRAFT, RECORD_STATUS_CANCELLED):
        raise frappe.ValidationError(
            f"Only a Draft or Cancelled fund record can be deleted (this one is {row.record_status})."
        )

    investor_flow_doc.remove(row)
    investor_flow_doc.save(ignore_permissions=True)


def approve_fund_record(investor_flow_id: str, record_name: str) -> Dict[str, Any]:
    """Posts the record's Journal Entry (Dr Paid to / Cr Paid from, party = investor) and counts it as received."""
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    row = _get_fund_record(investor_flow_doc, record_name)
    if (row.get("record_status") or RECORD_STATUS_DRAFT) != RECORD_STATUS_DRAFT:
        raise frappe.ValidationError(f"Only a Draft fund record can be approved (this one is {row.record_status}).")
    if investor_flow_doc.status != STATUS_APPROVED:
        raise frappe.ValidationError(
            f"Funds can be approved only for an Approved investment (current status: '{investor_flow_doc.status}')."
        )

    row.journal_entry = accounting.post_fund_entry(investor_flow_doc, row)
    row.record_status = RECORD_STATUS_APPROVED
    _refresh_fund_status(investor_flow_doc)
    _rebuild_repayment_schedule(investor_flow_doc)
    investor_flow_doc.save(ignore_permissions=True)
    return _record_dict(investor_flow_doc, row)


def cancel_fund_record(investor_flow_id: str, record_name: str) -> Dict[str, Any]:
    """
    Cancels an Approved record: its Journal Entry is cancelled, the amount no longer counts and the
    repayment schedule is rebuilt. (A Draft is not cancelled; it can be edited or deleted.)
    """
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    row = _get_fund_record(investor_flow_doc, record_name)
    status = row.get("record_status") or RECORD_STATUS_DRAFT
    if status != RECORD_STATUS_APPROVED:
        raise frappe.ValidationError(f"Only an Approved fund record can be cancelled (this one is {status}).")

    row.record_status = RECORD_STATUS_CANCELLED
    _refresh_fund_status(investor_flow_doc)
    # Rebuild first: if the schedule can't be rebuilt, nothing is cancelled.
    _rebuild_repayment_schedule(investor_flow_doc)
    accounting.cancel_journal_entry(row.journal_entry)
    investor_flow_doc.save(ignore_permissions=True)
    return _record_dict(investor_flow_doc, row)


def get_fund_records(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Every fund record (one row per receipt) with its investment and investor."""
    filters = [["parenttype", "=", DOCTYPE], ["parentfield", "=", FUND_TABLE_FIELD]]
    if args.get("record_status"):
        filters.append(["record_status", "in", _as_list(args.get("record_status"))])

    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        investor_ids = frappe.get_all("Customer", filters={"customer_name": ["like", search_term]}, pluck="name")
        parents = frappe.get_all(
            DOCTYPE,
            or_filters=[["name", "like", search_term], ["investor", "like", search_term]]
            + ([["investor", "in", investor_ids]] if investor_ids else []),
            pluck="name",
        )
        filters.append(["parent", "in", parents or [""]])

    query = dict(filters=filters, parent_doctype=DOCTYPE)
    rows = frappe.get_all(
        FUND_RECORD_DOCTYPE,
        fields=FUND_RECORD_FIELDS,
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        order_by="creation desc",
        **query,
    )
    total_records = len(frappe.get_all(FUND_RECORD_DOCTYPE, pluck="name", **query))
    total_pages = (total_records + page_size - 1) // page_size

    flows = {
        f.name: f
        for f in frappe.get_all(
            DOCTYPE,
            filters={"name": ["in", list({r.parent for r in rows}) or [""]]},
            fields=["name", "investor", "investment_amount", "status", "fund_status"],
        )
    }
    approved_by_flow: Dict[str, float] = {}
    if flows:
        for r in frappe.get_all(
            FUND_RECORD_DOCTYPE,
            filters={"parent": ["in", list(flows)], "parentfield": FUND_TABLE_FIELD,
                     "record_status": RECORD_STATUS_APPROVED},
            fields=["parent", "amount_paid"],
            parent_doctype=DOCTYPE,
        ):
            approved_by_flow[r.parent] = flt(approved_by_flow.get(r.parent, 0) + flt(r.amount_paid), 2)

    investor_names = _get_names("Customer", "customer_name", [f.investor for f in flows.values()])
    result = []
    for r in rows:
        flow = flows.get(r.parent)
        investment_amount = flt(flow.investment_amount, 2) if flow else 0
        result.append({
            **{f: r.get(f) for f in FUND_RECORD_FIELDS if f != "parent"},
            "record_status": r.record_status or RECORD_STATUS_DRAFT,
            "investment_id": r.parent,
            "investor_id": flow.investor if flow else r.investor_id,
            "investor": investor_names.get(flow.investor) if flow else r.investor_id,
            "investment_amount": investment_amount,
            "remaining_fund": max(flt(investment_amount - approved_by_flow.get(r.parent, 0), 2), 0),
            "investment_status": flow.status if flow else None,
            "fund_status": (flow.fund_status if flow else None) or FUND_STATUS_PENDING,
        })

    return result, total_records, total_pages


def get_investor_funds(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Investments that can receive funds (Approved) and fully funded ones (Paid), with their totals."""
    filters = [["status", "in", FUND_LIST_STATUSES]]
    if args.get("status"):
        filters.append(["status", "in", _as_list(args.get("status"))])
    if args.get("fund_status"):
        filters.append(["fund_status", "in", _as_list(args.get("fund_status"))])

    or_filters = None
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        investor_ids = frappe.get_all("Customer", filters={"customer_name": ["like", search_term]}, pluck="name")
        or_filters = [["name", "like", search_term], ["investor", "like", search_term]]
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    rows = frappe.get_all(
        DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=["name", "investor", "investment_amount", "fund_status", "status"],
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        order_by="modified desc",
    )
    total_records = len(frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name"))
    total_pages = (total_records + page_size - 1) // page_size

    records_by_flow: Dict[str, list] = {}
    if rows:
        for r in frappe.get_all(
            FUND_RECORD_DOCTYPE,
            filters={"parent": ["in", [x.name for x in rows]], "parentfield": FUND_TABLE_FIELD},
            fields=["parent", "idx", "amount_paid", "paid_date", "mode_of_payment", "record_status"],
            parent_doctype=DOCTYPE,
        ):
            records_by_flow.setdefault(r.parent, []).append(r)

    investor_names = _get_names("Customer", "customer_name", [r.investor for r in rows])
    result = []
    for row in rows:
        result.append({
            "name": row.name,
            "investor_id": row.investor,
            "investor": investor_names.get(row.investor) or row.investor,
            "status": row.status,
            **_fund_summary(row.investment_amount, records_by_flow.get(row.name, []), row.fund_status),
        })

    return result, total_records, total_pages


def get_investor_fund_by_id(investor_flow_id: str) -> Dict[str, Any]:
    """An investment's fund totals and every fund record."""
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    rows = sorted(_fund_rows(investor_flow_doc), key=lambda r: r.idx)

    return {
        "id": investor_flow_doc.name,
        "investor_id": investor_flow_doc.investor,
        "investor": frappe.db.get_value("Customer", investor_flow_doc.investor, "customer_name")
        or investor_flow_doc.investor,
        "status": investor_flow_doc.status,
        **_fund_summary(investor_flow_doc.investment_amount, rows, investor_flow_doc.fund_status),
        "funds": [_record_dict(investor_flow_doc, r) for r in rows],
    }


def get_record_fund_accounts() -> Dict[str, Any]:
    """Credit GL and the Debit GL of each Mode of Payment, for the Record Fund screen."""
    return accounting.get_record_fund_accounts()


def _receipt_interest(amount: float, rate: float, paid_date, maturity_date) -> float:
    """Interest on one receipt, calculated once: simple interest for the whole months from its paid date to maturity."""
    months = max(1, int((getdate(maturity_date) - getdate(paid_date)).days / AVERAGE_DAYS_PER_MONTH + 0.5))
    return flt(amount * rate / 1200 * months, 2)


def _split_equally(total: float, count: int) -> list:
    """total split into count equal parts (2 decimals); the last part takes the rounding difference."""
    each = flt(total / count, 2)
    return [each] * (count - 1) + [flt(total - each * (count - 1), 2)]


def _rebuild_repayment_schedule(investor_flow_doc):
    """
    Rebuilds the repayment schedule from the Approved fund records (called when a record is approved or
    an approved one is cancelled):
      - each receipt's interest is calculated once on its principal, from its paid date to maturity;
      - rows already due (on or before today) or already Accrued / Paid stay as they are;
      - the rest (principal and interest not yet in those rows) is split equally over the future payout
        dates; the last row takes the rounding difference.
    The result is saved as a new schedule version (the previous one stays in the history).
    """
    rate = flt(investor_flow_doc.interest_rate)
    maturity_date = getdate(investor_flow_doc.maturity_date)
    receipts = [r for r in _fund_rows(investor_flow_doc) if r.get("record_status") == RECORD_STATUS_APPROVED]
    principal_total = flt(sum(flt(r.amount_paid) for r in receipts), 2)
    interest_total = flt(
        sum(_receipt_interest(flt(r.amount_paid), rate, r.paid_date, maturity_date) for r in receipts), 2
    )

    current = current_schedule(investor_flow_doc)
    if principal_total <= 0 and not current:
        return

    today = getdate(nowdate())
    locked = [r for r in current if getdate(r.payment_date) <= today or r.status in (ROW_STATUS_ACCRUED, ROW_STATUS_PAID)]
    locked_dates = {getdate(r.payment_date) for r in locked}
    future_dates = [
        d for d in _payout_dates(
            investor_flow_doc.repayment_frequency,
            getdate(investor_flow_doc.first_repayment_date),
            maturity_date,
        )
        if d > today and d not in locked_dates
    ]

    remaining_principal = flt(principal_total - sum(flt(r.principal_amount) for r in locked), 2)
    remaining_interest = flt(interest_total - sum(flt(r.interest_amount) for r in locked), 2)
    if remaining_principal < 0 or remaining_interest < 0:
        raise frappe.ValidationError(
            "The schedule rows already due or paid include more principal / interest than the approved funds."
        )
    if not future_dates and (remaining_principal > 0 or remaining_interest > 0):
        raise frappe.ValidationError("No payout date is left after today to schedule the received fund.")

    # Penalty entered on a future row is kept when that date is still in the new schedule.
    penalty_by_date = {getdate(r.payment_date): flt(r.penalty_amount) for r in current if r not in locked}
    principals = _split_equally(remaining_principal, len(future_dates)) if future_dates else []
    interests = _split_equally(remaining_interest, len(future_dates)) if future_dates else []

    new_rows = [
        {f: r.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS + EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS} for r in locked
    ]
    for d, principal, interest in zip(future_dates, principals, interests):
        penalty = penalty_by_date.get(d, 0)
        new_rows.append({
            "payment_date": d,
            "principal_amount": principal,
            "interest_amount": interest,
            "penalty_amount": penalty,
            "total_payment": flt(principal + interest + penalty, 2),
            "status": ROW_STATUS_PENDING,
            "accrual_entry": None,
            "payout_entry": None,
        })
    new_rows.sort(key=lambda r: getdate(r["payment_date"]))

    def _key(rows):
        return [
            (str(getdate(r["payment_date"])), flt(r["principal_amount"], 2), flt(r["interest_amount"], 2),
             flt(r["penalty_amount"], 2), r.get("status"))
            for r in rows
        ]
    current_values = [
        {f: r.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS + EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS} for r in current
    ]
    if current and _key(current_values) == _key(new_rows):
        return

    version = (schedule_version(current[0]) + 1) if current else 1
    for values in new_rows:
        investor_flow_doc.append(SCHEDULE_TABLE_FIELD, {**values, "version": version})

    # Earning & Settlement details (read-only on screen).
    investor_flow_doc.amount_invested = cint(round(principal_total))
    investor_flow_doc.frequency = investor_flow_doc.repayment_frequency
    investor_flow_doc.mat_date = investor_flow_doc.maturity_date
    investor_flow_doc.rate_of_interest = investor_flow_doc.interest_rate
    investor_flow_doc.first_repay_date = investor_flow_doc.first_repayment_date
    investor_flow_doc.rate_of_penalty = investor_flow_doc.penalty_rate


def _get_earning_doc(investor_flow_id: str, for_update: bool = False):
    """Repayment Record exists once funds are approved (Fund Status Partial or Paid)."""
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    if (investor_flow_doc.fund_status or FUND_STATUS_PENDING) not in EARNING_FUND_STATUSES:
        raise frappe.ValidationError(
            "The repayment schedule is created when a fund record is approved "
            f"(Fund Status: '{investor_flow_doc.fund_status or FUND_STATUS_PENDING}')."
        )
    if for_update and investor_flow_doc.status == "Cancelled":
        raise frappe.ValidationError("This investment is Cancelled.")
    return investor_flow_doc


def get_investor_earnings(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Investments with approved funds (Fund Status Partial / Paid) and their main repayment fields."""
    filters = {"fund_status": ["in", EARNING_FUND_STATUSES]}
    if args.get("investment_product"):
        filters["investment_product"] = ["in", _as_list(args.get("investment_product"))]

    or_filters = None
    search = args.get("search")
    if search:
        search_term = f"%{str(search).strip()}%"
        investor_ids = frappe.get_all(
            "Customer", filters={"customer_name": ["like", search_term]}, pluck="name"
        )
        or_filters = [
            ["name", "like", search_term],
            ["investor", "like", search_term],
        ]
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    rows = frappe.get_all(
        DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=RETURN_FIELDS_EARNINGS_LIST,
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
        order_by="creation desc",
    )
    total_records = len(frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name"))
    total_pages = (total_records + page_size - 1) // page_size

    investor_names = _get_names("Customer", "customer_name", [r.investor for r in rows])
    product_names = _get_names(
        "Custom Investment Product", "product_name", [r.investment_product for r in rows]
    )
    for row in rows:
        row["investor_id"] = row.investor
        row["investor"] = investor_names.get(row.investor) or row.investor
        row["investment_product_name"] = (
            product_names.get(row.investment_product) or row.investment_product
        )

    return rows, total_records, total_pages


def _get_names(doctype: str, name_field: str, ids: list) -> Dict[str, str]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    return dict(frappe.get_all(doctype, filters={"name": ["in", ids]}, fields=["name", name_field], as_list=True))


def _schedule_row_dict(row, number: int) -> Dict[str, Any]:
    """A schedule row for the API; idx is its position (1, 2, …) within its version."""
    return {
        "name": row.name,
        "idx": number,
        **{f: row.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS + EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS},
        "version": schedule_version(row),
    }


def get_investor_earning_by_id(investor_flow_id: str) -> Dict[str, Any]:
    investor_flow_doc = _get_earning_doc(investor_flow_id)
    current = current_schedule(investor_flow_doc)

    # Details come from the approved contract's terms.
    result = {key: investor_flow_doc.get(term) for key, term in CONTRACT_TERM_FIELDS.items()}
    result.update({
        "id": investor_flow_doc.name,
        "status": investor_flow_doc.status,
        "fund_status": investor_flow_doc.fund_status or FUND_STATUS_PENDING,
        "investor_id": investor_flow_doc.investor,
        "investor": frappe.db.get_value("Customer", investor_flow_doc.investor, "customer_name")
        or investor_flow_doc.investor,
        "investment_product": investor_flow_doc.investment_product,
        "investment_product_name": frappe.db.get_value(
            "Custom Investment Product", investor_flow_doc.investment_product, "product_name"
        ) or investor_flow_doc.investment_product,
        "payment_date": investor_flow_doc.payment_date,
        "receive_entry": investor_flow_doc.get("receive_entry"),
        "renewed_to": investor_flow_doc.get("renewed_to"),
        "renewed_from": investor_flow_doc.get("renewed_from"),
        # The schedule in use is the highest version; earlier versions are history.
        "schedule_version": schedule_version(current[0]) if current else 1,
        SCHEDULE_TABLE_FIELD: [_schedule_row_dict(row, i) for i, row in enumerate(current, start=1)],
        "schedule_history": [
            {
                "version": entry["version"],
                "rows": [_schedule_row_dict(row, i) for i, row in enumerate(entry["rows"], start=1)],
            }
            for entry in schedule_history(investor_flow_doc)
        ],
    })
    return result


def _detail_value_changed(doc, field: str, value) -> bool:
    current = doc.get(CONTRACT_TERM_FIELDS[field])
    if field in ("mat_date", "first_repay_date"):
        return (getdate(value) if value else None) != (getdate(current) if current else None)
    if field == "frequency":
        return (value or None) != (current or None)
    try:
        return flt(value, 2) != flt(current, 2)
    except (TypeError, ValueError):
        return True


def _row_value_changed(row, field: str, value) -> bool:
    if field == "payment_date":
        return bool(value) and getdate(value) != getdate(row.payment_date)
    try:
        return flt(value, 2) != flt(row.get(field), 2)
    except (TypeError, ValueError):
        return True


def pay_investor_earning_row(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Pays one schedule row: accrues it first if needed, then posts the payout Journal Entry."""
    investor_flow_doc = _get_earning_doc(investor_flow_id, for_update=True)

    row_name = data.get("row")
    row = next((r for r in current_schedule(investor_flow_doc) if r.name == row_name), None)
    if not row:
        raise frappe.ValidationError(
            f"Schedule row '{row_name}' is not in the current schedule of this Investor Flow."
        )
    if row.status == ROW_STATUS_PAID:
        raise frappe.ValidationError(f"Schedule row {row.idx} is already Paid.")

    posting_date = _parse_date(data.get("payment_date") or nowdate(), "Payment Date")
    settings = accounting.get_accounting_settings()
    accounting.pay_row(investor_flow_doc, row, settings, posting_date, data.get("ref_no"))
    investor_flow_doc.save(ignore_permissions=True)

    return get_investor_earning_by_id(investor_flow_doc.name)


def close_investor_flow(investor_flow_id: str) -> Dict[str, Any]:
    """Maturity: when every schedule row is Paid, nothing is owed: Status -> Matured."""
    investor_flow_doc = _get_earning_doc(investor_flow_id, for_update=True)

    rows = current_schedule(investor_flow_doc)
    unpaid = [str(i) for i, r in enumerate(rows, start=1) if r.status != ROW_STATUS_PAID]
    if not rows or unpaid:
        raise frappe.ValidationError(
            "All schedule rows must be Paid before closing"
            + (f" (unpaid rows: {', '.join(unpaid)})." if unpaid else ".")
        )

    investor_flow_doc.status = STATUS_MATURED
    investor_flow_doc.save(ignore_permissions=True)
    return {"id": investor_flow_doc.name, "status": investor_flow_doc.status}


def update_investor_earning(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Edits the current repayment schedule. The details are read-only. An edit is saved as a new version:
    every row of the current schedule is copied with version max + 1 (edited values applied);
    earlier versions stay as history.
    """
    investor_flow_doc = _get_earning_doc(investor_flow_id, for_update=True)

    # The Earning & Settlement details are read-only; only the schedule rows can be edited.
    changed_details = [
        f for f in EARNING_DETAIL_FIELDS
        if f in data and _detail_value_changed(investor_flow_doc, f, data.get(f))
    ]
    if changed_details:
        raise frappe.ValidationError(
            f"Earning details cannot be edited ({', '.join(changed_details)}); only the schedule rows can."
        )

    current = current_schedule(investor_flow_doc)
    position = {row.name: i for i, row in enumerate(current, start=1)}
    # Values of the current schedule, edited below; saved as a new version if anything changed.
    new_values = {
        row.name: {f: row.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS + EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS}
        for row in current
    }

    schedule = data.get(SCHEDULE_TABLE_FIELD) or []
    if not isinstance(schedule, list):
        raise frappe.ValidationError("'schedule' must be a list of rows.")

    any_change = False
    for index, row_data in enumerate(schedule, start=1):
        row = next((r for r in current if r.name == row_data.get("name")), None)
        if not row:
            raise frappe.ValidationError(
                f"Schedule row {index}: '{row_data.get('name')}' is not in the current schedule."
            )
        number = position[row.name]
        changed = [
            f for f in EARNING_SCHEDULE_ROW_FIELDS
            if f in row_data and _row_value_changed(row, f, row_data.get(f))
        ]
        if not changed:
            continue
        # Paid rows are locked; accrued rows keep their date, principal and interest
        # (penalty can still be added; it is paid through Penalty Expense).
        if row.status == ROW_STATUS_PAID:
            raise frappe.ValidationError(f"Schedule row {number} is Paid and cannot be changed.")
        locked = {"payment_date", "principal_amount", "interest_amount"}
        if row.status == ROW_STATUS_ACCRUED and locked.intersection(changed):
            raise frappe.ValidationError(
                f"Schedule row {number} is Accrued: only Penalty and Total Payment can be changed."
            )
        values = new_values[row.name]
        if "payment_date" in changed:
            if not row_data.get("payment_date"):
                raise frappe.ValidationError(f"Schedule row {number}: Payment Date is required.")
            values["payment_date"] = _parse_date(row_data.get("payment_date"), f"Schedule row {number}: Payment Date")
        for field in EARNING_AMOUNT_FIELDS:
            if field in changed:
                try:
                    value = float(row_data.get(field))
                except (TypeError, ValueError):
                    raise frappe.ValidationError(f"Schedule row {number}: {field} must be a number.")
                if value < 0:
                    raise frappe.ValidationError(f"Schedule row {number}: {field} cannot be negative.")
                values[field] = value
        any_change = True

    if not any_change:
        return get_investor_earning_by_id(investor_flow_doc.name)

    # Edited schedule = a full new set of rows with version max + 1; the earlier rows stay as history.
    new_version = schedule_version(current[0]) + 1
    for row in current:
        investor_flow_doc.append(SCHEDULE_TABLE_FIELD, {**new_values[row.name], "version": new_version})

    investor_flow_doc.save(ignore_permissions=True)
    return get_investor_earning_by_id(investor_flow_doc.name)


# How far apart the payouts are for each Repayment Frequency.
SCHEDULE_FREQUENCY_STEP = {
    "Weekly": ("days", 7),
    "Bi-Weekly": ("days", 14),
    "Monthly": ("months", 1),
    "Quarterly": ("months", 3),
    "Yearly": ("months", 12),
}
MAX_SCHEDULE_ROWS = 600
AVERAGE_DAYS_PER_MONTH = 30.4375


def get_schedule(data: Dict[str, Any]) -> Dict[str, Any]:
    required_fields = [
        "investment_amount", "repayment_frequency", "maturity_date",
        "interest_rate", "first_repayment_date",
    ]
    missing = [f for f in required_fields if data.get(f) in (None, "")]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    # Same field rules as create/update (numbers, frequency, dates, maturity after first repayment).
    _validate_investor_flow_payload(data, is_update=True)

    first_repayment_date = getdate(data.get("first_repayment_date"))
    if first_repayment_date <= getdate(nowdate()):
        raise frappe.ValidationError("First Repayment Date must be in the future.")

    return _calculate_schedule(
        amount=flt(data.get("investment_amount")),
        rate=flt(data.get("interest_rate")),
        penalty_rate=flt(data.get("penalty_rate")),
        frequency=data.get("repayment_frequency"),
        first_repayment_date=first_repayment_date,
        maturity_date=getdate(data.get("maturity_date")),
    )


def _payout_dates(frequency: str, first_repayment_date, maturity_date) -> list:
    """Payout dates: first repayment date, then one every step, and finally the maturity date."""
    unit, step = SCHEDULE_FREQUENCY_STEP[frequency]
    dates = []
    index = 0
    current = first_repayment_date
    while current < maturity_date:
        if len(dates) >= MAX_SCHEDULE_ROWS:
            raise frappe.ValidationError(
                f"Schedule is too long (more than {MAX_SCHEDULE_ROWS} payouts). "
                "Use a longer repayment frequency or an earlier maturity date."
            )
        dates.append(current)
        index += 1
        if unit == "months":
            current = getdate(add_months(first_repayment_date, index * step))
        else:
            current = getdate(add_days(first_repayment_date, index * step))
    dates.append(maturity_date)
    return dates


def _calculate_schedule(
    amount: float, rate: float, penalty_rate: float, frequency: str, first_repayment_date, maturity_date
) -> Dict[str, Any]:
    today = getdate(nowdate())
    # Simple interest for the whole months between today and maturity.
    total_months = max(1, int((maturity_date - today).days / AVERAGE_DAYS_PER_MONTH + 0.5))
    total_interest = amount * rate / 1200 * total_months

    dates = _payout_dates(frequency, first_repayment_date, maturity_date)

    # Principal and interest (on the amount invested, for the whole tenure) are both split equally
    # across the payouts; the last payout takes the rounding difference so the totals match exactly.
    count = len(dates)
    principal_each = flt(amount / count, 2)
    per_payment = flt(total_interest / count, 2)
    last_principal = flt(amount - principal_each * (count - 1), 2)
    last_interest = flt(total_interest - per_payment * (count - 1), 2)

    schedule = []
    for i, date in enumerate(dates):
        is_last = i == count - 1
        principal = last_principal if is_last else principal_each
        interest = last_interest if is_last else per_payment
        schedule.append({
            "installment_no": i + 1,
            "date": str(date),
            "principal": principal,
            "interest": interest,
            "total": flt(principal + interest, 2),
        })

    return {
        "investment_amount": amount,
        "interest_rate": rate,
        "penalty_rate": penalty_rate,
        "repayment_frequency": frequency,
        "first_repayment_date": str(first_repayment_date),
        "maturity_date": str(maturity_date),
        "total_months": total_months,
        "total_interest": flt(total_interest, 2),
        "per_payment": flt(per_payment, 2),
        "count": len(dates),
        "schedule": schedule,
    }