"""
Investor Flow accounting (all GL accounts come from Custom Investor Settings).

1. Record Fund        : Paid from Investor Creditor GL -> Paid to <Mode of Payment GL>:
                        Dr <Mode of Payment GL> (Cash / Cheque / Bank Draft / Wire Transfer)
                        / Cr Investor Creditor GL (party = investor)
2. Accrue a row       : not used any more (no accrual, no Payable GL).
   (Investor Payout entries: see payouts.py.)
3. Pay a row          : Dr Interest Expense (interest)  / Cr Investor Income GL (party = investor)
                        Dr Penalty Expense  (penalty)   / Cr Investor Income GL (party = investor)
                        Dr Investor Creditor GL (principal, party = investor) / Cr Company Bank (principal)
"""
import frappe
from typing import Dict, Any, List, Iterable
from frappe.utils import flt, getdate, nowdate, cint

from .utils import current_schedule
from .constant import (
    DOCTYPE,
    SETTINGS_DOCTYPE,
    SETTINGS_ACCOUNT_FIELDS,
    PAYMENT_MODE_ACCOUNT_FIELDS,
    SCHEDULE_TABLE_FIELD,
    STATUS_RECEIVED,
    ROW_STATUS_PENDING,
    ROW_STATUS_ACCRUED,
    ROW_STATUS_PAID,
)


# Needed to save the settings; the others can be set as they are needed.
SETTINGS_REQUIRED_ON_SAVE = ["investor_creditor_account"]

# Used by the repayment steps (payout); checked when set.
PAYOUT_ACCOUNT_FIELDS = [
    "company_bank_account", "investor_creditor_account",
    "interest_expense_account", "penalty_expense_account",
]
# Must be set for an Investor Payout. Company Bank Account is not: the payout pays from the Mode of Payment GL
# (it is still needed by pay_row, used by Maturity).
PAYOUT_REQUIRED_ACCOUNT_FIELDS = [
    "investor_creditor_account", "interest_expense_account", "penalty_expense_account",
]


def _ensure_settings_doctype():
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        raise frappe.ValidationError(f"DocType '{SETTINGS_DOCTYPE}' does not exist yet.")
    if not frappe.get_meta(SETTINGS_DOCTYPE).issingle:
        raise frappe.ValidationError(f"DocType '{SETTINGS_DOCTYPE}' must be a Single DocType (tick 'Is Single').")


def validate_settings_accounts(accounts: Dict[str, str], required: Iterable[str]) -> Dict[str, Any]:
    """
    Checks the accounts that are set (exist, not group, one company); the user picks the right GL,
    so the kind of account is not checked. The required ones must be set.
    Returns the company and the account details.
    """
    missing = [SETTINGS_ACCOUNT_FIELDS[f] for f in required if not accounts.get(f)]
    if missing:
        raise frappe.ValidationError(f"Set these accounts in {SETTINGS_DOCTYPE} first: {', '.join(missing)}.")

    selected = {field: account for field, account in accounts.items() if account}
    details = {
        row.name: row
        for row in frappe.get_all(
            "Account",
            filters={"name": ["in", list(selected.values())]},
            fields=["name", "account_name", "account_number", "company", "is_group",
                    "account_type", "root_type", "account_currency"],
        )
    }

    for field, account_name in selected.items():
        label = SETTINGS_ACCOUNT_FIELDS[field]
        account = details.get(account_name)
        if not account:
            raise frappe.DoesNotExistError(f"{label} '{account_name}' does not exist.")
        if cint(account.is_group):
            raise frappe.ValidationError(f"{label} '{account.name}' is a group account.")

    companies = {d.company for d in details.values()}
    if len(companies) > 1:
        raise frappe.ValidationError(f"All accounts in {SETTINGS_DOCTYPE} must belong to the same company.")

    return {"company": next(iter(companies), None), "details": details}


def _settings_accounts() -> Dict[str, str]:
    _ensure_settings_doctype()
    settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    return {field: settings.get(field) for field in SETTINGS_ACCOUNT_FIELDS}


def describe_account(account) -> str:
    """'<Account Name> (<Account Number>)', e.g. 'SBI Current Account (852103641078)'."""
    return f"{account.account_name} ({account.account_number})" if account.account_number else account.account_name


def get_fund_accounts(payment_mode: str) -> Dict[str, Any]:
    """Record Fund: Debit = the GL set for the Mode of Payment; Credit = Investor Creditor GL."""
    mode_field = PAYMENT_MODE_ACCOUNT_FIELDS.get(payment_mode)
    if not mode_field:
        raise frappe.ValidationError(f"Mode of Payment must be one of: {', '.join(PAYMENT_MODE_ACCOUNT_FIELDS)}.")

    accounts = _settings_accounts()
    checked = validate_settings_accounts(
        {f: accounts[f] for f in ("investor_creditor_account", mode_field)},
        required=("investor_creditor_account", mode_field),
    )
    # Paid from "Fund received" (Investor Creditor GL) -> Paid to the Mode of Payment GL:
    # Dr Mode of Payment GL / Cr Investor Creditor GL.
    debit = checked["details"][accounts[mode_field]]
    credit = checked["details"][accounts["investor_creditor_account"]]
    return {
        "company": checked["company"],
        "debit_gl": debit.name,
        "debit_gl_description": describe_account(debit),
        "credit_gl": credit.name,
        "credit_gl_description": describe_account(credit),
        "party_accounts": {credit.name},
    }


def get_record_fund_accounts() -> Dict[str, Any]:
    """For the Record Fund screen: the Credit GL and the Debit GL of each Mode of Payment (if set)."""
    accounts = _settings_accounts()
    selected = {f: accounts[f] for f in ["investor_creditor_account", *PAYMENT_MODE_ACCOUNT_FIELDS.values()]}
    checked = validate_settings_accounts(selected, required=("investor_creditor_account",))
    details = checked["details"]

    def info(account_name):
        if not account_name:
            return None
        account = details[account_name]
        return {"account": account.name, "description": describe_account(account), "currency": account.account_currency}

    return {
        "company": checked["company"],
        "credit": info(accounts["investor_creditor_account"]),
        "debit_by_mode": {mode: info(accounts[field]) for mode, field in PAYMENT_MODE_ACCOUNT_FIELDS.items()},
    }


def get_accounting_settings() -> Dict[str, Any]:
    """Accounts for the repayment steps (accrual / payout), all in one company."""
    accounts = _settings_accounts()
    selected = {f: accounts[f] for f in PAYOUT_ACCOUNT_FIELDS}
    checked = validate_settings_accounts(selected, required=PAYOUT_REQUIRED_ACCOUNT_FIELDS)

    return {
        **selected,
        "company": checked["company"],
        "company_bank_currency": (
            checked["details"][accounts["company_bank_account"]].account_currency
            if accounts.get("company_bank_account") else None
        ),
        # Lines on these accounts carry the investor as party (per-investor ledger).
        "party_accounts": {accounts["investor_creditor_account"]},
        "investor_income_account": accounts.get("investor_income_account"),
    }


def get_settings_for_setup() -> Dict[str, Any]:
    """Current settings (the screen searches accounts itself)."""
    _ensure_settings_doctype()
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    return {
        "company": frappe.defaults.get_user_default("Company"),
        "accounts": {field: settings.get(field) for field in SETTINGS_ACCOUNT_FIELDS},
        "labels": SETTINGS_ACCOUNT_FIELDS,
        "required": SETTINGS_REQUIRED_ON_SAVE,
    }


def update_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves the accounts after the same checks the Journal Entries rely on."""
    _ensure_settings_doctype()
    accounts = {field: (data.get(field) or "").strip() for field in SETTINGS_ACCOUNT_FIELDS}
    validate_settings_accounts(accounts, required=SETTINGS_REQUIRED_ON_SAVE)

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    for field, account in accounts.items():
        settings.set(field, account or None)
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


def post_fund_entry(investor_flow_doc, row) -> str:
    """
    1. Approve a fund record: Dr <row.debit_gl> (Mode of Payment GL) / Cr <row.credit_gl>
    (Investor Creditor GL, party = investor), using the GLs stored on the row.
    """
    company = frappe.db.get_value("Account", row.debit_gl, "company")
    creditor = _settings_accounts().get("investor_creditor_account")
    return _make_journal_entry(
        {"company": company, "party_accounts": {creditor}},
        investor_flow_doc.investor,
        row.paid_date,
        f"Fund received for Investor Flow {investor_flow_doc.name} (record {row.idx})",
        [
            {"account": row.debit_gl, "debit": flt(row.amount_paid, 2)},
            {"account": row.credit_gl, "credit": flt(row.amount_paid, 2)},
        ],
        reference_no=row.reference_number,
    )


def cancel_journal_entry(journal_entry: str):
    """Cancels a submitted Journal Entry (ERPNext reverses its ledger entries)."""
    if not journal_entry:
        return
    doc = frappe.get_doc("Journal Entry", journal_entry)
    if doc.docstatus == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()


# No accrual: interest is booked straight from the Interest Expense GL when it is paid (Payable GL not used).
# def accrue_row(investor_flow_doc, row, settings, posting_date=None) -> str:
#     """2. Accrue one schedule row on its due date: Dr Interest (+ Penalty) Expense / Cr Interest Payable."""
#     interest, penalty = flt(row.interest_amount, 2), flt(row.penalty_amount, 2)
#     entry = _make_journal_entry(
#         settings,
#         investor_flow_doc.investor,
#         posting_date or row.payment_date,
#         f"Interest accrued for Investor Flow {investor_flow_doc.name}, schedule row {row.idx}",
#         [
#             {"account": settings["interest_expense_account"], "debit": interest},
#             {"account": settings["penalty_expense_account"], "debit": penalty},
#             {"account": settings["interest_payable_account"], "credit": interest + penalty},
#         ],
#     )
#     row.status = ROW_STATUS_ACCRUED
#     row.accrual_entry = entry
#     return entry
#
#
# def _accrued_amount(row, settings) -> float:
#     """Interest + penalty credited to Interest Payable by the row's accrual entry."""
#     if not row.accrual_entry:
#         # A renewal's deferred-interest row is Accrued without an entry of its own:
#         # its interest was booked in Interest Payable before the renewal.
#         return flt(row.interest_amount, 2) if row.status == ROW_STATUS_ACCRUED else 0
#     credits = frappe.get_all(
#         "Journal Entry Account",
#         filters={"parent": row.accrual_entry, "account": settings["interest_payable_account"]},
#         pluck="credit_in_account_currency",
#     )
#     return flt(sum(flt(c) for c in credits), 2)


def pay_row(
    investor_flow_doc, row, settings, posting_date, reference_no: str = None, principal_to_pay: float = None
) -> str:
    """
    3. Pay one schedule row (no accrual):
       Dr Interest Expense + Penalty Expense / Cr Investor Income GL; Dr Investor Creditor GL / Cr Company Bank.
    principal_to_pay (Renew): pay only this much of the row's principal; the rest stays in the Investor
    Creditor GL and is carried into the renewed investment.
    """
    missing = [SETTINGS_ACCOUNT_FIELDS[f] for f in ("company_bank_account", "investor_income_account")
               if not settings.get(f)]
    if missing:
        raise frappe.ValidationError(f"Set these accounts in {SETTINGS_DOCTYPE} first: {', '.join(missing)}.")

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

    entry = _make_journal_entry(
        settings,
        investor_flow_doc.investor,
        posting_date,
        f"Payout for Investor Flow {investor_flow_doc.name}, schedule row {row.idx}",
        [
            {"account": settings["interest_expense_account"], "debit": interest},
            {"account": settings["penalty_expense_account"], "debit": penalty},
            {"account": settings["investor_income_account"], "credit": flt(interest + penalty, 2)},
            {"account": settings["investor_creditor_account"], "debit": principal_paid},
            {"account": settings["company_bank_account"], "credit": principal_paid},
        ],
        reference_no=reference_no,
    )
    row.status = ROW_STATUS_PAID
    row.payout_entry = entry
    return entry


# No accrual: the daily job is no longer scheduled (hooks.py) and is kept here commented out.
# def accrue_due_rows():
#     """Daily job (no longer scheduled, see hooks.py): accrue every Pending schedule row whose payment date has arrived."""
#     today = getdate(nowdate())
#     flow_ids = frappe.get_all(
#         "Custom Investor Earning Schedule",
#         filters={
#             "parenttype": DOCTYPE,
#             "parentfield": SCHEDULE_TABLE_FIELD,
#             "status": ROW_STATUS_PENDING,
#             "payment_date": ["<=", today],
#         },
#         pluck="parent",
#         distinct=True,
#     )
#     if not flow_ids:
#         return
#
#     try:
#         settings = get_accounting_settings()
#     except Exception:
#         frappe.log_error(title="Investor Flow accrual: settings incomplete")
#         return
#
#     for flow_id in flow_ids:
#         try:
#             investor_flow_doc = frappe.get_doc(DOCTYPE, flow_id)
#             if investor_flow_doc.fund_status not in ("Partial", "Paid") or investor_flow_doc.status == "Cancelled":
#                 continue
#             for row in current_schedule(investor_flow_doc):
#                 if row.status == ROW_STATUS_PENDING and getdate(row.payment_date) <= today:
#                     accrue_row(investor_flow_doc, row, settings)
#             investor_flow_doc.save(ignore_permissions=True)
#             frappe.db.commit()
#         except Exception:
#             frappe.db.rollback()
#             frappe.log_error(title=f"Investor Flow accrual failed: {flow_id}")
