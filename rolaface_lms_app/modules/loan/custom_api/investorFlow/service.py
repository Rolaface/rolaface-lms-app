import frappe
from typing import Tuple, Dict, Any
from .constant import (
    DOCTYPE,
    ALLOWED_INVESTOR_FLOW_FIELDS,
    RETURN_FIELDS_GET_ALL,
    RETURN_FIELDS_GET_BY_ID,
    ALLOWED_SORT_FIELDS,
    DEFAULT_STATUS,
    STATUS_ACTION_MAP,
    ALLOWED_STATUS_TRANSITIONS,
    CONTRACT_STATUS_PENDING,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_PAID,
    PAYMENT_MODES,
    PAYMENT_FIELDS,
    PAYMENT_GL_FIELDS,
    RETURN_FIELDS_BANK_ACCOUNT,
    STATUS_RECEIVED,
    REPAYMENT_FREQUENCIES,
    SCHEDULE_TABLE_FIELD,
    EARNING_DETAIL_FIELDS,
    EARNING_SCHEDULE_ROW_FIELDS,
    EARNING_AMOUNT_FIELDS,
    RETURN_FIELDS_EARNINGS_LIST,
)
from .utils import _validate_investor_flow_payload, _build_investor_flow_filters, _as_list, _parse_date
from frappe.utils import getdate, add_months, add_days, flt, nowdate, cint, validate_email_address


def create_investor_flow(data: Dict[str, Any]) -> Dict[str, Any]:
    _validate_investor_flow_payload(data, is_update=False)

    investor_flow_doc = frappe.new_doc(DOCTYPE)

    for field in ALLOWED_INVESTOR_FLOW_FIELDS:
        if field in data and data.get(field) is not None:
            investor_flow_doc.set(field, data.get(field))

    investor_flow_doc.status = DEFAULT_STATUS
    investor_flow_doc.insert(ignore_permissions=True)
    return get_investor_flow_by_id(investor_flow_doc.name)


def update_investor_flow(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")

    investor_flow_doc = frappe.get_doc(DOCTYPE, investor_flow_id)

    _validate_investor_flow_payload(data, is_update=True, existing_doc=investor_flow_doc)
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

    missing = [f for f in ("to", "subject", "file_id") if not data.get(f)]
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
    investor_flow_doc.contract_status = CONTRACT_STATUS_SENT
    investor_flow_doc.save(ignore_permissions=True)

    return {
        "id": investor_flow_doc.name,
        "contract_status": investor_flow_doc.contract_status,
        "mail_sent": investor_flow_doc.mail_sent,
        "subject": investor_flow_doc.subject,
        "file_id": file_doc.name,
        "file_url": file_doc.file_url,
    }


def receive_payment(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)

    missing = [f for f in PAYMENT_FIELDS if data.get(f) in (None, "")]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")

    if STATUS_RECEIVED not in ALLOWED_STATUS_TRANSITIONS.get(investor_flow_doc.status or DEFAULT_STATUS, []):
        raise frappe.ValidationError(
            f"Payment cannot be received for an Investor Flow in status '{investor_flow_doc.status}'."
        )

    if investor_flow_doc.contract_status != CONTRACT_STATUS_SENT:
        raise frappe.ValidationError(
            f"Payment can be received only when Contract Status is '{CONTRACT_STATUS_SENT}' "
            f"(current: '{investor_flow_doc.contract_status}')."
        )

    try:
        amount_paid = float(data.get("amount_paid"))
    except (TypeError, ValueError):
        raise frappe.ValidationError("Amount Paid must be a number.")
    if amount_paid <= 0 or amount_paid != int(amount_paid):
        raise frappe.ValidationError("Amount Paid must be a whole number greater than 0.")
    amount_paid = int(amount_paid)

    if data.get("payment_mode") not in PAYMENT_MODES:
        raise frappe.ValidationError(f"Mode of Payment must be one of: {', '.join(PAYMENT_MODES)}.")

    payment_date = getdate(data.get("payment_date"))

    # Paid From is the investor's Bank Account; its GL account goes in the Journal Entry.
    paid_from, paid_to = data.get("paid_from"), data.get("paid_to")
    bank_account = frappe.db.get_value(
        "Bank Account", paid_from, ["party_type", "party", "account", "disabled"], as_dict=True
    )
    if not bank_account:
        raise frappe.DoesNotExistError(f"Paid From bank account '{paid_from}' does not exist.")
    if bank_account.party_type != "Customer" or bank_account.party != investor_flow_doc.investor:
        raise frappe.ValidationError(
            f"Bank account '{paid_from}' does not belong to investor '{investor_flow_doc.investor}'."
        )
    if cint(bank_account.disabled):
        raise frappe.ValidationError(f"Bank account '{paid_from}' is disabled.")

    if not bank_account.account:
        raise frappe.ValidationError(f"Bank account '{paid_from}' has no Company Account.")

    # Journal Entry: credit the Bank Account's Company Account, debit Paid To.
    credit_account, to_gl = bank_account.account, paid_to
    if credit_account == to_gl:
        raise frappe.ValidationError("Paid From and Paid To must be different accounts.")

    accounts = {}
    for label, account in (("Paid From", credit_account), ("Paid To", to_gl)):
        account_details = frappe.db.get_value(
            "Account", account, ["company", "account_type", "is_group"], as_dict=True
        )
        if not account_details:
            raise frappe.DoesNotExistError(f"{label} account '{account}' does not exist.")
        if cint(account_details.is_group):
            raise frappe.ValidationError(f"{label} account '{account}' is a group account.")
        accounts[account] = account_details

    company = accounts[to_gl].company
    if accounts[credit_account].company != company:
        raise frappe.ValidationError("Paid From and Paid To accounts must belong to the same company.")

    def _account_row(account, debit, credit):
        row = {
            "account": account,
            "debit_in_account_currency": debit,
            "credit_in_account_currency": credit,
        }
        # ERPNext needs a party on Receivable / Payable accounts.
        if accounts[account].account_type in ("Receivable", "Payable"):
            row.update({"party_type": "Customer", "party": investor_flow_doc.investor})
        return row

    journal_entry = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": company,
        "posting_date": payment_date,
        "cheque_no": data.get("ref_no"),
        "cheque_date": payment_date,
        "user_remark": (
            f"Investment received for Investor Flow {investor_flow_doc.name} "
            f"via {data.get('payment_mode')}"
        ),
        "accounts": [
            _account_row(to_gl, amount_paid, 0),
            _account_row(credit_account, 0, amount_paid),
        ],
    })
    journal_entry.insert(ignore_permissions=True)
    journal_entry.submit()

    investor_flow_doc.payment_date = payment_date
    investor_flow_doc.ref_no = data.get("ref_no")
    investor_flow_doc.payment_mode = data.get("payment_mode")
    investor_flow_doc.amount_paid = amount_paid
    investor_flow_doc.paid_from = paid_from
    investor_flow_doc.paid_to = paid_to
    # Paid GL = the Bank Account's Company Account (credited in the Journal Entry).
    investor_flow_doc.paid_gl = credit_account
    investor_flow_doc.to_gl = to_gl
    investor_flow_doc.contract_status = CONTRACT_STATUS_PAID
    investor_flow_doc.status = STATUS_RECEIVED
    _set_earnings(investor_flow_doc, amount_paid)
    investor_flow_doc.save(ignore_permissions=True)

    return {
        "id": investor_flow_doc.name,
        "status": investor_flow_doc.status,
        "contract_status": investor_flow_doc.contract_status,
        "journal_entry": journal_entry.name,
        **{field: investor_flow_doc.get(field) for field in PAYMENT_FIELDS + PAYMENT_GL_FIELDS},
    }


def _set_earnings(investor_flow_doc, amount_paid: int):
    """Earning & Settlement: details copied from the terms (amount = Amount Paid) and the payout schedule."""
    investor_flow_doc.amount_invested = amount_paid
    investor_flow_doc.frequency = investor_flow_doc.repayment_frequency
    investor_flow_doc.mat_date = investor_flow_doc.maturity_date
    investor_flow_doc.rate_of_interest = investor_flow_doc.interest_rate
    investor_flow_doc.first_repay_date = investor_flow_doc.first_repayment_date
    investor_flow_doc.rate_of_penalty = investor_flow_doc.penalty_rate

    result = _calculate_schedule(
        amount=flt(amount_paid),
        rate=flt(investor_flow_doc.interest_rate),
        penalty_rate=flt(investor_flow_doc.penalty_rate),
        frequency=investor_flow_doc.repayment_frequency,
        first_repayment_date=getdate(investor_flow_doc.first_repayment_date),
        maturity_date=getdate(investor_flow_doc.maturity_date),
    )

    investor_flow_doc.set(SCHEDULE_TABLE_FIELD, [])
    for row in result["schedule"]:
        investor_flow_doc.append(SCHEDULE_TABLE_FIELD, {
            "payment_date": row["date"],
            "principal_amount": row["principal"],
            "interest_amount": row["interest"],
            "penalty_amount": 0,
            "total_payment": row["total"],
        })


def _get_earning_doc(investor_flow_id: str):
    investor_flow_doc = _get_existing_investor_flow(investor_flow_id)
    if investor_flow_doc.status != STATUS_RECEIVED:
        raise frappe.ValidationError(
            f"Earnings exist only for a Received Investor Flow (current status: '{investor_flow_doc.status}')."
        )
    return investor_flow_doc


def get_investor_earnings(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Received Investor Flows with the main Earning & Settlement fields."""
    filters = {"status": STATUS_RECEIVED}
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


def get_investor_earning_by_id(investor_flow_id: str) -> Dict[str, Any]:
    investor_flow_doc = _get_earning_doc(investor_flow_id)

    result = {field: investor_flow_doc.get(field) for field in EARNING_DETAIL_FIELDS}
    result.update({
        "id": investor_flow_doc.name,
        "status": investor_flow_doc.status,
        "investor_id": investor_flow_doc.investor,
        "investor": frappe.db.get_value("Customer", investor_flow_doc.investor, "customer_name")
        or investor_flow_doc.investor,
        "investment_product": investor_flow_doc.investment_product,
        "investment_product_name": frappe.db.get_value(
            "Custom Investment Product", investor_flow_doc.investment_product, "product_name"
        ) or investor_flow_doc.investment_product,
        "payment_date": investor_flow_doc.payment_date,
        SCHEDULE_TABLE_FIELD: [
            {"name": row.name, "idx": row.idx, **{f: row.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS}}
            for row in sorted(investor_flow_doc.get(SCHEDULE_TABLE_FIELD) or [], key=lambda r: r.idx)
        ],
    })
    return result


def _validate_earning_details(data: Dict[str, Any], existing_doc):
    if "amount_invested" in data:
        try:
            value = float(data.get("amount_invested"))
        except (TypeError, ValueError):
            raise frappe.ValidationError("Amount Invested must be a number.")
        if value <= 0 or value != int(value):
            raise frappe.ValidationError("Amount Invested must be a whole number greater than 0.")

    for field, label in (("rate_of_interest", "Rate of Interest"), ("rate_of_penalty", "Rate of Penalty")):
        if field in data and data.get(field) not in (None, ""):
            try:
                value = float(data.get(field))
            except (TypeError, ValueError):
                raise frappe.ValidationError(f"{label} must be a number.")
            if value < 0 or value > 100:
                raise frappe.ValidationError(f"{label} must be between 0 and 100.")

    if "frequency" in data and data.get("frequency") not in REPAYMENT_FREQUENCIES:
        raise frappe.ValidationError(f"Frequency must be one of: {', '.join(REPAYMENT_FREQUENCIES)}.")

    for field, label in (("mat_date", "Maturity Date"), ("first_repay_date", "First Repay Date")):
        if field in data and not data.get(field):
            raise frappe.ValidationError(f"{label} is required.")

    first_repay_date = _parse_date(
        data.get("first_repay_date") or existing_doc.first_repay_date, "First Repay Date"
    )
    mat_date = _parse_date(data.get("mat_date") or existing_doc.mat_date, "Maturity Date")
    if mat_date <= first_repay_date:
        raise frappe.ValidationError("Maturity Date must be after the First Repay Date.")


def update_investor_earning(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Edits the Earning & Settlement details and existing schedule rows (rows cannot be added or removed)."""
    investor_flow_doc = _get_earning_doc(investor_flow_id)

    details = {f: data[f] for f in EARNING_DETAIL_FIELDS if f in data}
    _validate_earning_details(details, investor_flow_doc)
    for field, value in details.items():
        investor_flow_doc.set(field, value)

    rows_by_name = {row.name: row for row in investor_flow_doc.get(SCHEDULE_TABLE_FIELD) or []}
    schedule = data.get(SCHEDULE_TABLE_FIELD) or []
    if not isinstance(schedule, list):
        raise frappe.ValidationError("'schedule' must be a list of rows.")

    for index, row_data in enumerate(schedule, start=1):
        row = rows_by_name.get(row_data.get("name"))
        if not row:
            raise frappe.ValidationError(
                f"Schedule row {index}: '{row_data.get('name')}' does not belong to this Investor Flow."
            )
        if "payment_date" in row_data:
            if not row_data.get("payment_date"):
                raise frappe.ValidationError(f"Schedule row {row.idx}: Payment Date is required.")
            row.payment_date = _parse_date(row_data.get("payment_date"), f"Schedule row {row.idx}: Payment Date")
        for field in EARNING_AMOUNT_FIELDS:
            if field in row_data:
                try:
                    value = float(row_data.get(field))
                except (TypeError, ValueError):
                    raise frappe.ValidationError(f"Schedule row {row.idx}: {field} must be a number.")
                if value < 0:
                    raise frappe.ValidationError(f"Schedule row {row.idx}: {field} cannot be negative.")
                row.set(field, value)

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


def _calculate_schedule(
    amount: float, rate: float, penalty_rate: float, frequency: str, first_repayment_date, maturity_date
) -> Dict[str, Any]:
    today = getdate(nowdate())
    # Simple interest for the whole months between today and maturity.
    total_months = max(1, int((maturity_date - today).days / AVERAGE_DAYS_PER_MONTH + 0.5))
    total_interest = amount * rate / 1200 * total_months

    # Payout dates: first repayment date, then one every step, and finally the maturity date.
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