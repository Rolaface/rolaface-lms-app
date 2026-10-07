"""
Investor Flow accounting (all GL accounts come from Custom Investor Settings).

1. Receive investment : Dr Company Bank            / Cr Investor Deposits (party = investor)
2. Accrue a row       : Dr Interest Expense
                        Dr Penalty Expense (if any) / Cr Interest Payable (party = investor)
3. Pay a row          : Dr Investor Deposits (principal)
                        Dr Interest Payable (accrued interest + penalty)
                        Dr Penalty Expense (penalty added after accrual)
                                                    / Cr Company Bank (total)
"""
import frappe
from typing import Dict, Any, List
from frappe.utils import flt, getdate, nowdate, cint

from .constant import (
    DOCTYPE,
    SETTINGS_DOCTYPE,
    SETTINGS_ACCOUNT_FIELDS,
    SCHEDULE_TABLE_FIELD,
    STATUS_RECEIVED,
    ROW_STATUS_PENDING,
    ROW_STATUS_ACCRUED,
    ROW_STATUS_PAID,
)


# Which accounts each settings field accepts (also used to fill the settings dropdowns).
# The investor (a Customer) is the party on the two liability lines. ERPNext allows party type Customer
# only on Receivable accounts, so those liability accounts must have a blank Account Type.
SETTINGS_ACCOUNT_RULES = {
    "company_bank_account": {"root_type": "Asset", "account_type": ["Bank", "Cash"]},
    "investor_deposit_account": {"root_type": "Liability", "account_type": [""]},
    "interest_payable_account": {"root_type": "Liability", "account_type": [""]},
    "interest_expense_account": {"root_type": "Expense"},
    "penalty_expense_account": {"root_type": "Expense"},
}

SETTINGS_RULE_TEXT = {
    "company_bank_account": "an Asset account with Account Type Bank or Cash",
    "investor_deposit_account": "a Liability account with a blank Account Type",
    "interest_payable_account": "a Liability account with a blank Account Type",
    "interest_expense_account": "an Expense account",
    "penalty_expense_account": "an Expense account",
}


def _ensure_settings_doctype():
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        raise frappe.ValidationError(f"DocType '{SETTINGS_DOCTYPE}' does not exist yet.")
    if not frappe.get_meta(SETTINGS_DOCTYPE).issingle:
        raise frappe.ValidationError(f"DocType '{SETTINGS_DOCTYPE}' must be a Single DocType (tick 'Is Single').")


def validate_settings_accounts(accounts: Dict[str, str]) -> Dict[str, Any]:
    """Checks the five accounts (exist, not group, right kind, one company). Returns their details."""
    missing = [label for field, label in SETTINGS_ACCOUNT_FIELDS.items() if not accounts.get(field)]
    if missing:
        raise frappe.ValidationError(f"Set these accounts in {SETTINGS_DOCTYPE} first: {', '.join(missing)}.")

    details = {
        row.name: row
        for row in frappe.get_all(
            "Account",
            filters={"name": ["in", list(accounts.values())]},
            fields=["name", "company", "is_group", "account_type", "root_type", "account_currency"],
        )
    }

    for field, label in SETTINGS_ACCOUNT_FIELDS.items():
        account = details.get(accounts[field])
        if not account:
            raise frappe.DoesNotExistError(f"{label} '{accounts[field]}' does not exist.")
        if cint(account.is_group):
            raise frappe.ValidationError(f"{label} '{account.name}' is a group account.")
        rule = SETTINGS_ACCOUNT_RULES[field]
        if account.root_type != rule["root_type"] or (
            "account_type" in rule and (account.account_type or "") not in rule["account_type"]
        ):
            raise frappe.ValidationError(
                f"{label} '{account.name}' must be {SETTINGS_RULE_TEXT[field]}."
            )

    company = details[accounts["company_bank_account"]].company
    if any(d.company != company for d in details.values()):
        raise frappe.ValidationError(f"All accounts in {SETTINGS_DOCTYPE} must belong to the same company.")

    return {"company": company, "details": details}


def get_accounting_settings() -> Dict[str, Any]:
    """The five GL accounts from Custom Investor Settings, all in one company."""
    _ensure_settings_doctype()
    settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    accounts = {field: settings.get(field) for field in SETTINGS_ACCOUNT_FIELDS}
    checked = validate_settings_accounts(accounts)

    return {
        **accounts,
        "company": checked["company"],
        "company_bank_currency": checked["details"][accounts["company_bank_account"]].account_currency,
        # Lines on these accounts carry the investor as party (per-investor ledger).
        "party_accounts": {accounts["investor_deposit_account"], accounts["interest_payable_account"]},
    }


def get_settings_for_setup() -> Dict[str, Any]:
    """Current settings and, per field, the accounts it accepts in the user's default company."""
    _ensure_settings_doctype()
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    company = frappe.defaults.get_user_default("Company")

    options = {}
    for field, rule in SETTINGS_ACCOUNT_RULES.items():
        filters = {"is_group": 0, "disabled": 0, "root_type": rule["root_type"]}
        if company:
            filters["company"] = company
        rows = frappe.get_all(
            "Account", filters=filters, fields=["name", "account_type"], order_by="name asc"
        )
        if "account_type" in rule:
            rows = [r for r in rows if (r.account_type or "") in rule["account_type"]]
        options[field] = [r.name for r in rows]

    return {
        "company": company,
        "accounts": {field: settings.get(field) for field in SETTINGS_ACCOUNT_FIELDS},
        "labels": SETTINGS_ACCOUNT_FIELDS,
        "rules": SETTINGS_RULE_TEXT,
        "options": options,
    }


def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves the five accounts after the same checks the Journal Entries rely on."""
    _ensure_settings_doctype()
    accounts = {field: (data.get(field) or "").strip() for field in SETTINGS_ACCOUNT_FIELDS}
    validate_settings_accounts(accounts)

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    for field, account in accounts.items():
        settings.set(field, account)
    settings.save(ignore_permissions=True)
    frappe.clear_document_cache(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE)

    return get_settings_for_setup()


def _make_journal_entry(
    settings: Dict[str, Any],
    investor: str,
    posting_date,
    remark: str,
    lines: List[Dict[str, Any]],
    reference_no: str = None,
) -> str:
    """Creates and submits a Journal Entry. lines: [{"account", "debit", "credit"}]; zero lines are skipped."""
    accounts = []
    for line in lines:
        debit, credit = flt(line.get("debit"), 2), flt(line.get("credit"), 2)
        if not debit and not credit:
            continue
        row = {
            "account": line["account"],
            "debit_in_account_currency": debit,
            "credit_in_account_currency": credit,
        }
        if line["account"] in settings["party_accounts"]:
            row.update({"party_type": "Customer", "party": investor})
        accounts.append(row)

    journal_entry = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": settings["company"],
        "posting_date": getdate(posting_date),
        "cheque_no": reference_no,
        "cheque_date": getdate(posting_date) if reference_no else None,
        "user_remark": remark,
        "accounts": accounts,
    })
    journal_entry.insert(ignore_permissions=True)
    journal_entry.submit()
    return journal_entry.name


def post_receive_entry(investor_flow_doc, settings, amount: float, posting_date, reference_no: str) -> str:
    """1. Investor invests: Dr Company Bank / Cr Investor Deposits."""
    return _make_journal_entry(
        settings,
        investor_flow_doc.investor,
        posting_date,
        f"Investment received for Investor Flow {investor_flow_doc.name}",
        [
            {"account": settings["company_bank_account"], "debit": amount},
            {"account": settings["investor_deposit_account"], "credit": amount},
        ],
        reference_no=reference_no,
    )


def accrue_row(investor_flow_doc, row, settings, posting_date=None) -> str:
    """2. Accrue one schedule row on its due date: Dr Interest (+ Penalty) Expense / Cr Interest Payable."""
    interest, penalty = flt(row.interest_amount, 2), flt(row.penalty_amount, 2)
    entry = _make_journal_entry(
        settings,
        investor_flow_doc.investor,
        posting_date or row.payment_date,
        f"Interest accrued for Investor Flow {investor_flow_doc.name}, schedule row {row.idx}",
        [
            {"account": settings["interest_expense_account"], "debit": interest},
            {"account": settings["penalty_expense_account"], "debit": penalty},
            {"account": settings["interest_payable_account"], "credit": interest + penalty},
        ],
    )
    row.status = ROW_STATUS_ACCRUED
    row.accrual_entry = entry
    return entry


def _accrued_amount(row, settings) -> float:
    """Interest + penalty credited to Interest Payable by the row's accrual entry."""
    if not row.accrual_entry:
        return 0
    credits = frappe.get_all(
        "Journal Entry Account",
        filters={"parent": row.accrual_entry, "account": settings["interest_payable_account"]},
        pluck="credit_in_account_currency",
    )
    return flt(sum(flt(c) for c in credits), 2)


def pay_row(
    investor_flow_doc, row, settings, posting_date, reference_no: str = None, principal_to_pay: float = None
) -> str:
    """
    3. Pay one schedule row: Dr Investor Deposits + Interest Payable (+ late Penalty) / Cr Company Bank.
    principal_to_pay (Renew): pay only this much of the row's principal in cash; the rest stays in
    Investor Deposits and is carried into the renewed investment.
    """
    principal = flt(row.principal_amount, 2)
    interest, penalty = flt(row.interest_amount, 2), flt(row.penalty_amount, 2)
    total = flt(principal + interest + penalty, 2)
    principal_paid = principal if principal_to_pay is None else flt(principal_to_pay, 2)
    if principal_paid < 0 or principal_paid > principal:
        raise frappe.ValidationError(f"Schedule row {row.idx}: invalid principal to pay ({principal_paid}).")

    if flt(row.total_payment, 2) != total:
        raise frappe.ValidationError(
            f"Schedule row {row.idx}: Total Payment ({flt(row.total_payment, 2)}) must equal "
            f"Principal + Interest + Penalty ({total})."
        )

    # Rows saved before the status field existed have no status: treat them as Pending.
    if row.status in (None, "", ROW_STATUS_PENDING):
        # Paid before its due date: accrue on the payout date, not in the future.
        accrue_row(investor_flow_doc, row, settings, min(getdate(row.payment_date), getdate(posting_date)))

    accrued = _accrued_amount(row, settings)
    # Penalty entered after the accrual has not gone through Interest Payable yet.
    late_penalty = flt(interest + penalty - accrued, 2)
    if late_penalty < 0:
        raise frappe.ValidationError(
            f"Schedule row {row.idx}: Interest + Penalty ({flt(interest + penalty, 2)}) is less than "
            f"the amount already accrued ({accrued})."
        )

    entry = _make_journal_entry(
        settings,
        investor_flow_doc.investor,
        posting_date,
        f"Payout for Investor Flow {investor_flow_doc.name}, schedule row {row.idx}",
        [
            {"account": settings["investor_deposit_account"], "debit": principal_paid},
            {"account": settings["interest_payable_account"], "debit": accrued},
            {"account": settings["penalty_expense_account"], "debit": late_penalty},
            {"account": settings["company_bank_account"], "credit": flt(principal_paid + interest + penalty, 2)},
        ],
        reference_no=reference_no,
    )
    row.status = ROW_STATUS_PAID
    row.payout_entry = entry
    return entry


def accrue_due_rows():
    """Daily job: accrue every Pending schedule row whose payment date has arrived."""
    today = getdate(nowdate())
    flow_ids = frappe.get_all(
        "Custom Investor Earning Schedule",
        filters={
            "parenttype": DOCTYPE,
            "parentfield": SCHEDULE_TABLE_FIELD,
            "status": ROW_STATUS_PENDING,
            "payment_date": ["<=", today],
        },
        pluck="parent",
        distinct=True,
    )
    if not flow_ids:
        return

    try:
        settings = get_accounting_settings()
    except Exception:
        frappe.log_error(title="Investor Flow accrual: settings incomplete")
        return

    for flow_id in flow_ids:
        try:
            investor_flow_doc = frappe.get_doc(DOCTYPE, flow_id)
            if investor_flow_doc.status != STATUS_RECEIVED:
                continue
            for row in investor_flow_doc.get(SCHEDULE_TABLE_FIELD) or []:
                if row.status == ROW_STATUS_PENDING and getdate(row.payment_date) <= today:
                    accrue_row(investor_flow_doc, row, settings)
            investor_flow_doc.save(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Investor Flow accrual failed: {flow_id}")
