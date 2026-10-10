"""
Investor Flow renewal: renewing an investment on the SAME Custom Investor Flow after it has expired.

Payment Status (payment_status):
  Pending  - the current schedule is running and money is still due before its maturity.
  Expired  - today is after the maturity date and money is still due. The schedule can no longer be
             edited; its rows can still be paid (the investor takes the money back), or it is renewed.
  Paid     - every row of the current schedule is Paid.
  Renewed  - running under an approved renewal.
The maturity in force is the last payment date of the current schedule (the latest version), so it is
right for the original contract and for every renewal after it.

A renewal can be added at expiry (Expired) or mid-contract (Pending / Renewed; effective date from today up to
the maturity date). Either way, the unpaid rows of the current schedule (principal + the interest fixed for them
when the contract started) are what is owed; paid rows are left out.

Renewal (renewal_status): Draft -> Approved -> (Cancelled). Draft can be edited / deleted, Approved can only
be cancelled, Cancelled can be deleted. Only one renewal is held at a time; a new one (when the renewed
contract expires again) overwrites the renewal fields.

On Approve:
  1. every unpaid row of the current schedule that is still Pending is accrued (Interest Payable is booked);
  2. one Journal Entry is posted on the effective date (party = investor):
       Capitalization      Dr Interest Payable  / Cr Investor Creditor               (interest becomes principal)
       Partial Settlement  Dr Interest Payable + Dr Investor Creditor (rest of the settlement) / Cr Company Bank
                           (if the settlement is less than the interest, the rest of the interest is
                            capitalized: Cr Investor Creditor)
       Rollover / Extended "Pay on renewal date": Dr Interest Payable / Cr Company Bank
       Rollover / Extended "Defer to an agreed future date": no entry; the interest stays in Interest Payable
                           and is paid by a separate row on the deferred date (already Accrued).
  3. the new schedule (renewal terms) is saved as the next version; the old one stays in the history.
On Cancel: the Journal Entry is cancelled and the schedule in force before the renewal is restored as the
next version (only while nothing of the renewed schedule has been accrued or paid).
"""
import frappe
from typing import Dict, Any, List, Tuple, Optional
from frappe.utils import add_months, cint, flt, getdate, nowdate

from .constant import (
    DOCTYPE,
    SCHEDULE_TABLE_FIELD,
    EARNING_FUND_STATUSES,
    EARNING_SCHEDULE_ROW_FIELDS,
    EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS,
    REPAYMENT_FREQUENCIES,
    ROW_STATUS_PENDING,
    ROW_STATUS_ACCRUED,
    ROW_STATUS_PAID,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_RENEWED,
    PAYMENT_STATUS_EXPIRED,
    RENEWAL_STATUS_DRAFT,
    RENEWAL_STATUS_APPROVED,
    RENEWAL_STATUS_CANCELLED,
    RENEWAL_DELETABLE_STATUSES,
    RENEWAL_STRUCTURES,
    RENEWAL_CAPITALIZATION,
    RENEWAL_PARTIAL_SETTLEMENT,
    RENEWAL_INTEREST_SEPARATE,
    INTEREST_PAY_ON_RENEWAL,
    INTEREST_DEFER,
    INTEREST_SETTLEMENTS,
    RENEWAL_INPUT_FIELDS,
    RENEWAL_ALL_FIELDS,
    CONTRACT_STATUS_PENDING,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_PAID,
)
from .utils import _as_list, _parse_date, current_schedule, schedule_version
from . import accounting, service


# ------------------------------ Payment Status ------------------------------

def current_maturity(rows) -> Optional[Any]:
    """Maturity date in force: the last payment date of the current schedule."""
    return max(getdate(r.payment_date) for r in rows) if rows else None


def _payment_status(doc, today=None) -> Optional[str]:
    rows = current_schedule(doc)
    if not rows:
        return None
    today = getdate(today or nowdate())
    if all(r.status == ROW_STATUS_PAID for r in rows):
        return PAYMENT_STATUS_PAID
    if today > current_maturity(rows):
        return PAYMENT_STATUS_EXPIRED
    if doc.get("renewal_status") == RENEWAL_STATUS_APPROVED:
        return PAYMENT_STATUS_RENEWED
    return PAYMENT_STATUS_PENDING


def refresh_payment_status(doc, today=None) -> Optional[str]:
    """Sets payment_status on the document (not saved). Returns the status."""
    status = _payment_status(doc, today)
    if status:
        doc.payment_status = status
    return status


def sync_payment_status(doc) -> Optional[str]:
    """Works out the Payment Status from the schedule now and saves it if it changed (no daily job needed)."""
    status = _payment_status(doc)
    if status and status != doc.get("payment_status"):
        frappe.db.set_value(DOCTYPE, doc.name, "payment_status", status, update_modified=False)
        # Read (GET) requests are not committed by Frappe; keep the corrected status.
        frappe.db.commit()
        doc.payment_status = status
    return status or doc.get("payment_status")


def refresh_payment_statuses():
    """Daily job: Pending / Renewed investments past their maturity with money due become Expired."""
    names = frappe.get_all(
        DOCTYPE,
        filters={"fund_status": ["in", EARNING_FUND_STATUSES], "status": ["!=", "Cancelled"]},
        pluck="name",
    )
    for name in names:
        try:
            doc = frappe.get_doc(DOCTYPE, name)
            status = _payment_status(doc)
            if status and status != doc.get("payment_status"):
                frappe.db.set_value(DOCTYPE, name, "payment_status", status, update_modified=False)
                frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"Investor Flow payment status refresh failed: {name}")


def is_expired(doc) -> bool:
    return _payment_status(doc) == PAYMENT_STATUS_EXPIRED


# When a renewal can be added: at expiry (Expired), or mid-contract while it is still running.
RENEWAL_AT_EXPIRY = "At expiry"
RENEWAL_MID_CONTRACT = "Mid-contract"


def renewal_kind(doc) -> Optional[str]:
    """At expiry (Expired), Mid-contract (Pending / Renewed: running with money due), or None (cannot renew)."""
    if (doc.get("fund_status") or "") not in EARNING_FUND_STATUSES or doc.get("status") == "Cancelled":
        return None
    status = _payment_status(doc)
    if status == PAYMENT_STATUS_EXPIRED:
        return RENEWAL_AT_EXPIRY
    if status in (PAYMENT_STATUS_PENDING, PAYMENT_STATUS_RENEWED):
        return RENEWAL_MID_CONTRACT
    return None


# -------------------------------- Helpers --------------------------------

def _get_doc(investor_flow_id: str):
    if not investor_flow_id or not frappe.db.exists(DOCTYPE, investor_flow_id):
        raise frappe.DoesNotExistError(f"Investor Flow '{investor_flow_id}' does not exist.")
    return frappe.get_doc(DOCTYPE, investor_flow_id)


def _get_renewal_doc(investor_flow_id: str):
    doc = _get_doc(investor_flow_id)
    if not doc.get("renewal_status"):
        raise frappe.ValidationError(f"Investor Flow '{doc.name}' has no renewal.")
    return doc


def _outstanding(rows) -> Tuple[float, float]:
    """(principal, interest + penalty) still owed on the unpaid rows of the current schedule."""
    unpaid = [r for r in rows if r.status != ROW_STATUS_PAID]
    principal = flt(sum(flt(r.principal_amount) for r in unpaid), 2)
    interest = flt(sum(flt(r.interest_amount) + flt(r.penalty_amount) for r in unpaid), 2)
    return principal, interest


def _number(data, field, label, required=True) -> Optional[float]:
    value = data.get(field)
    if value in (None, ""):
        if required:
            raise frappe.ValidationError(f"{label} is required.")
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise frappe.ValidationError(f"{label} must be a number.")


def _contract_summary(doc) -> Dict[str, Any]:
    """Section 1 - the contract in force: its schedule, maturity and what is still owed."""
    rows = current_schedule(doc)
    principal, interest = _outstanding(rows)
    renewed = doc.get("renewal_status") == RENEWAL_STATUS_APPROVED
    return {
        "id": doc.name,
        "investor_id": doc.investor,
        "investor": frappe.db.get_value("Customer", doc.investor, "customer_name") or doc.investor,
        "investor_email": frappe.db.get_value("Customer", doc.investor, "email_id"),
        "investment_product": doc.investment_product,
        "investment_product_name": frappe.db.get_value(
            "Custom Investment Product", doc.investment_product, "product_name"
        ) or doc.investment_product,
        "status": doc.status,
        "payment_status": _payment_status(doc),
        "renewal_kind": renewal_kind(doc),
        # Principal and terms of the contract in force (the original one, or the last approved renewal).
        "contract_principal": flt(sum(flt(r.principal_amount) for r in rows), 2),
        "contract_maturity": str(current_maturity(rows)) if rows else None,
        "contract_interest_rate": flt(doc.renewal_interest_rate if renewed else doc.interest_rate),
        "contract_frequency": (doc.payment_frequency if renewed else doc.repayment_frequency),
        "contract_penalty_rate": flt(doc.renewal_penalty_rate if renewed else doc.penalty_rate),
        "original_investment_amount": flt(doc.investment_amount),
        "original_maturity_date": str(getdate(doc.maturity_date)) if doc.maturity_date else None,
        "outstanding_principal": principal,
        "unpaid_interest": interest,
        "rows_total": len(rows),
        "rows_paid": len([r for r in rows if r.status == ROW_STATUS_PAID]),
    }


# ------------------------------ Calculations ------------------------------

def _renewed_principal(structure: str, principal: float, interest: float, settlement: float) -> float:
    if structure == RENEWAL_CAPITALIZATION:
        return flt(principal + interest, 2)
    if structure == RENEWAL_PARTIAL_SETTLEMENT:
        return flt(principal + interest - settlement, 2)
    return flt(principal, 2)  # Principal Rollover / Extended Maturity


def _validated_terms(doc, data: Dict[str, Any]) -> Dict[str, Any]:
    """Checks the renewal input against the contract in force; returns the values to save (incl. calculated)."""
    rows = current_schedule(doc)
    if not rows:
        raise frappe.ValidationError("This investment has no repayment schedule to renew.")
    principal, interest = _outstanding(rows)
    maturity = current_maturity(rows)

    structure = data.get("renewal_structure")
    if structure not in RENEWAL_STRUCTURES:
        raise frappe.ValidationError(f"Renewal Structure must be one of: {', '.join(RENEWAL_STRUCTURES)}.")

    if not data.get("renewal_effective_date"):
        raise frappe.ValidationError("Renewal Effective Date is required.")
    effective = _parse_date(data.get("renewal_effective_date"), "Renewal Effective Date")
    kind = renewal_kind(doc)
    if kind is None:
        raise frappe.ValidationError(
            f"This investment cannot be renewed (Payment Status: {_payment_status(doc) or '-'})."
        )
    if kind == RENEWAL_AT_EXPIRY and effective < maturity:
        raise frappe.ValidationError(
            f"Renewal Effective Date cannot be before the current maturity date ({maturity})."
        )
    if kind == RENEWAL_MID_CONTRACT and not (getdate(nowdate()) <= effective <= maturity):
        raise frappe.ValidationError(
            f"For a renewal during the contract, the Renewal Effective Date must be from today "
            f"up to the current maturity date ({maturity})."
        )

    settlement = 0.0
    if structure == RENEWAL_PARTIAL_SETTLEMENT:
        settlement = flt(_number(data, "settlement_amount", "Settlement Amount"), 2)
        if settlement <= 0 or settlement >= flt(principal + interest, 2):
            raise frappe.ValidationError(
                f"Settlement Amount must be more than 0 and less than the amount owed "
                f"({flt(principal + interest, 2):,.2f} = principal {principal:,.2f} + interest {interest:,.2f})."
            )

    interest_settlement, interest_settlement_date = None, None
    if structure in RENEWAL_INTEREST_SEPARATE and interest > 0:
        interest_settlement = data.get("interest_settlement")
        if interest_settlement not in INTEREST_SETTLEMENTS:
            raise frappe.ValidationError(
                f"Interest Settlement must be one of: {', '.join(INTEREST_SETTLEMENTS)}."
            )

    rate = _number(data, "renewal_interest_rate", "Interest Rate")
    if rate < 0 or rate > 100:
        raise frappe.ValidationError("Interest Rate must be between 0 and 100.")
    penalty = _number(data, "renewal_penalty_rate", "Penalty Rate", required=False)
    if penalty is not None and (penalty < 0 or penalty > 100):
        raise frappe.ValidationError("Penalty Rate must be between 0 and 100.")

    frequency = data.get("payment_frequency")
    if frequency not in REPAYMENT_FREQUENCIES:
        raise frappe.ValidationError(f"Payment Frequency must be one of: {', '.join(REPAYMENT_FREQUENCIES)}.")

    tenure = _number(data, "renewal_tenure", "Renewal Tenure")
    if tenure <= 0 or tenure != int(tenure):
        raise frappe.ValidationError("Renewal Tenure must be a whole number of months greater than 0.")
    tenure = int(tenure)
    # The new maturity always follows from the effective date and the tenure, so they cannot conflict.
    new_maturity = getdate(add_months(effective, tenure))

    if not data.get("renewal_first_repayment_date"):
        raise frappe.ValidationError("First Payment Date is required.")
    first_payment = _parse_date(data.get("renewal_first_repayment_date"), "First Payment Date")
    if first_payment <= effective or first_payment > new_maturity:
        raise frappe.ValidationError(
            f"First Payment Date must be after the effective date ({effective}) "
            f"and on or before the new maturity date ({new_maturity})."
        )

    if interest_settlement == INTEREST_DEFER:
        if not data.get("interest_settlement_date"):
            raise frappe.ValidationError("Interest Settlement Date is required when the interest is deferred.")
        interest_settlement_date = _parse_date(data.get("interest_settlement_date"), "Interest Settlement Date")
        if interest_settlement_date <= effective or interest_settlement_date > new_maturity:
            raise frappe.ValidationError(
                f"Interest Settlement Date must be after the effective date ({effective}) "
                f"and on or before the new maturity date ({new_maturity})."
            )

    renewed = _renewed_principal(structure, principal, interest, settlement)
    if renewed <= 0:
        raise frappe.ValidationError("Renewed principal must be more than 0.")

    _validate_product_limits(doc.investment_product, renewed, rate, tenure)

    return {
        "renewal_structure": structure,
        "renewal_effective_date": effective,
        "settlement_amount": settlement if structure == RENEWAL_PARTIAL_SETTLEMENT else 0,
        "interest_settlement": interest_settlement,
        "interest_settlement_date": interest_settlement_date,
        "renewal_interest_rate": rate,
        "payment_frequency": frequency,
        "renewal_tenure": tenure,
        "renewal_first_repayment_date": first_payment,
        "renewal_penalty_rate": penalty or 0,
        "reason_for_renewal": data.get("reason_for_renewal"),
        "renewed_principal": renewed,
        "new_maturity_date": new_maturity,
        "renewal_outstanding_principal": principal,
        "renewal_unpaid_interest": interest,
    }


def _validate_product_limits(product: str, principal: float, rate: float, tenure: int):
    """The renewed contract must stay within the product limits, like a new investment."""
    limits = frappe.db.get_value(
        "Custom Investment Product", product,
        ["product_name", "minimum_investment", "maximum_investment", "min_interest_rate",
         "maximum_interest_rate", "minimum_tenure", "maximum_tenure"],
        as_dict=True,
    )
    if not limits:
        return
    name = limits.product_name
    if flt(limits.minimum_investment) and principal < flt(limits.minimum_investment):
        raise frappe.ValidationError(
            f"Renewed principal ({principal:,.2f}) is below the Minimum Investment of {name} "
            f"({flt(limits.minimum_investment):,.2f})."
        )
    if flt(limits.maximum_investment) and principal > flt(limits.maximum_investment):
        raise frappe.ValidationError(
            f"Renewed principal ({principal:,.2f}) is above the Maximum Investment of {name} "
            f"({flt(limits.maximum_investment):,.2f})."
        )
    if flt(limits.maximum_interest_rate) and not (
        flt(limits.min_interest_rate) <= rate <= flt(limits.maximum_interest_rate)
    ):
        raise frappe.ValidationError(
            f"Interest Rate must be between {flt(limits.min_interest_rate):g}% and "
            f"{flt(limits.maximum_interest_rate):g}% (limits of {name})."
        )
    if cint(limits.maximum_tenure) and not (cint(limits.minimum_tenure) <= tenure <= cint(limits.maximum_tenure)):
        raise frappe.ValidationError(
            f"Renewal Tenure must be between {cint(limits.minimum_tenure)} and {cint(limits.maximum_tenure)} "
            f"months (limits of {name})."
        )


def _schedule_rows(values: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    The renewed schedule, same method as a new investment: simple interest on the renewed principal for
    the tenure; principal and interest split equally over the payout dates (the last takes the rounding).
    A deferred interest is one extra row (interest only) on its date, already Accrued.
    """
    dates = service._payout_dates(
        values["payment_frequency"], getdate(values["renewal_first_repayment_date"]),
        getdate(values["new_maturity_date"]),
    )
    principal = flt(values["renewed_principal"], 2)
    interest_total = flt(principal * flt(values["renewal_interest_rate"]) / 1200 * cint(values["renewal_tenure"]), 2)
    principals = service._split_equally(principal, len(dates))
    interests = service._split_equally(interest_total, len(dates))

    rows = [
        {
            "payment_date": d,
            "principal_amount": p,
            "interest_amount": i,
            "penalty_amount": 0,
            "total_payment": flt(p + i, 2),
            "status": ROW_STATUS_PENDING,
            "accrual_entry": None,
            "payout_entry": None,
        }
        for d, p, i in zip(dates, principals, interests)
    ]
    if values.get("interest_settlement") == INTEREST_DEFER and flt(values["renewal_unpaid_interest"]) > 0:
        unpaid = flt(values["renewal_unpaid_interest"], 2)
        rows.append({
            "payment_date": getdate(values["interest_settlement_date"]),
            "principal_amount": 0,
            "interest_amount": unpaid,
            "penalty_amount": 0,
            "total_payment": unpaid,
            # Booked in Interest Payable before the renewal; it must not be accrued again.
            "status": ROW_STATUS_ACCRUED,
            "accrual_entry": None,
            "payout_entry": None,
        })
    rows.sort(key=lambda r: getdate(r["payment_date"]))
    return rows


def _rows_for_api(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {**{k: (str(v) if k == "payment_date" else v) for k, v in r.items()}, "idx": i}
        for i, r in enumerate(rows, start=1)
    ]


# --------------------------------- Read ---------------------------------

LIST_FIELDS = [
    "name", "investor", "investment_product", "renewal_structure", "renewal_effective_date",
    "renewed_principal", "renewal_interest_rate", "renewal_tenure", "new_maturity_date", "payment_frequency",
    "renewal_status", "renewal_contract_status", "payment_status", "modified",
]


def get_renewals(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Investments that have a renewal (any Renewal Status)."""
    filters = [["renewal_status", "is", "set"]]
    if args.get("renewal_status"):
        filters.append(["renewal_status", "in", _as_list(args.get("renewal_status"))])
    if args.get("renewal_structure"):
        filters.append(["renewal_structure", "in", _as_list(args.get("renewal_structure"))])

    or_filters = None
    search = args.get("search")
    if search:
        term = f"%{str(search).strip()}%"
        or_filters = [["name", "like", term], ["investor", "like", term]]
        investor_ids = frappe.get_all("Customer", filters={"customer_name": ["like", term]}, pluck="name")
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    rows = frappe.get_all(
        DOCTYPE, filters=filters, or_filters=or_filters, fields=LIST_FIELDS,
        limit_start=(page - 1) * page_size, limit_page_length=page_size, order_by="modified desc",
    )
    total = len(frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name"))

    names = service._get_names("Customer", "customer_name", [r.investor for r in rows])
    products = service._get_names("Custom Investment Product", "product_name", [r.investment_product for r in rows])
    for r in rows:
        r["investor_id"] = r.investor
        r["investor"] = names.get(r.investor) or r.investor
        r["investment_product_name"] = products.get(r.investment_product) or r.investment_product
    return rows, total, (total + page_size - 1) // page_size


def get_renewal_candidates(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Investments that can get a new renewal: Expired, and no Draft renewal waiting."""
    filters = {"fund_status": ["in", EARNING_FUND_STATUSES], "status": ["!=", "Cancelled"]}
    or_filters = None
    if search:
        term = f"%{str(search).strip()}%"
        or_filters = [["name", "like", term], ["investor", "like", term]]
        investor_ids = frappe.get_all("Customer", filters={"customer_name": ["like", term]}, pluck="name")
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])

    result = []
    for name in frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name"):
        doc = frappe.get_doc(DOCTYPE, name)
        if doc.get("renewal_status") == RENEWAL_STATUS_DRAFT or not renewal_kind(doc):
            continue
        summary = _contract_summary(doc)
        result.append({k: summary[k] for k in (
            "id", "investor_id", "investor", "investment_product_name", "contract_principal",
            "contract_maturity", "outstanding_principal", "unpaid_interest", "payment_status", "renewal_kind",
        )})
    return result


def get_renewal_context(investor_flow_id: str) -> Dict[str, Any]:
    """Section 1 for a new renewal, plus the terms of the contract in force to start from."""
    doc = _get_doc(investor_flow_id)
    return _contract_summary(doc)


def get_renewal_by_id(investor_flow_id: str) -> Dict[str, Any]:
    doc = _get_renewal_doc(investor_flow_id)
    result = {"contract": _contract_summary(doc)}
    for field in RENEWAL_ALL_FIELDS:
        value = doc.get(field)
        result[field] = str(value) if hasattr(value, "isoformat") else value
    result["id"] = doc.name
    return result


def preview_renewal_schedule(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """The schedule the renewal will create (nothing is saved)."""
    doc = _get_doc(investor_flow_id)
    values = _validated_terms(doc, data)
    rows = _schedule_rows(values)
    return {
        "renewed_principal": values["renewed_principal"],
        "new_maturity_date": str(values["new_maturity_date"]),
        "outstanding_principal": values["renewal_outstanding_principal"],
        "unpaid_interest": values["renewal_unpaid_interest"],
        # Interest of the renewed contract (the deferred row is old interest, already booked).
        "total_interest": flt(sum(flt(r["interest_amount"]) for r in rows if r["status"] == ROW_STATUS_PENDING), 2),
        "count": len(rows),
        "schedule": _rows_for_api(rows),
    }


# --------------------------------- Write ---------------------------------

def save_renewal(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates (Add Renewal) or edits a Draft renewal."""
    doc = _get_doc(investor_flow_id)
    status = doc.get("renewal_status")
    if status != RENEWAL_STATUS_DRAFT:
        # A new renewal: at expiry, or during the contract while money is still due.
        if not renewal_kind(doc):
            raise frappe.ValidationError(
                "This investment cannot be renewed: it needs a repayment schedule with money still due "
                f"(Payment Status: {_payment_status(doc) or '-'})."
            )
        # A previous renewal's details (incl. its mail) are replaced by the new one.
        for field in RENEWAL_ALL_FIELDS:
            doc.set(field, None)
        doc.renewal_contract_status = CONTRACT_STATUS_PENDING

    values = _validated_terms(doc, data)
    for field, value in values.items():
        doc.set(field, value)
    doc.renewal_status = RENEWAL_STATUS_DRAFT
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return get_renewal_by_id(doc.name)


def delete_renewal(investor_flow_id: str):
    """Removes a Draft or Cancelled renewal (clears the renewal fields)."""
    doc = _get_renewal_doc(investor_flow_id)
    if doc.renewal_status not in RENEWAL_DELETABLE_STATUSES:
        raise frappe.ValidationError(
            f"Only a Draft or Cancelled renewal can be deleted (this one is {doc.renewal_status})."
        )
    for field in RENEWAL_ALL_FIELDS:
        doc.set(field, None)
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)


def _renewal_journal_lines(values: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    interest = flt(values["renewal_unpaid_interest"], 2)
    structure = values["renewal_structure"]
    payable, creditor, bank = (
        settings["interest_payable_account"], settings["investor_creditor_account"], settings["company_bank_account"],
    )
    if structure == RENEWAL_CAPITALIZATION:
        return [{"account": payable, "debit": interest}, {"account": creditor, "credit": interest}]
    if structure == RENEWAL_PARTIAL_SETTLEMENT:
        settlement = flt(values["settlement_amount"], 2)
        principal_part = flt(settlement - interest, 2)
        return [
            {"account": payable, "debit": interest},
            # Settlement above the interest reduces principal; below it, the rest of the interest is capitalized.
            {"account": creditor, "debit": principal_part} if principal_part > 0
            else {"account": creditor, "credit": -principal_part},
            {"account": bank, "credit": settlement},
        ]
    if values.get("interest_settlement") == INTEREST_PAY_ON_RENEWAL:
        return [{"account": payable, "debit": interest}, {"account": bank, "credit": interest}]
    return []  # deferred interest (or nothing owed): no entry


def approve_renewal(investor_flow_id: str) -> Dict[str, Any]:
    doc = _get_renewal_doc(investor_flow_id)
    if doc.renewal_status != RENEWAL_STATUS_DRAFT:
        raise frappe.ValidationError(f"Only a Draft renewal can be approved (this one is {doc.renewal_status}).")
    if not renewal_kind(doc):
        raise frappe.ValidationError("Nothing is owed on this investment any more (it may have been paid); it cannot be renewed.")

    # Re-check with today's figures: a payout after the renewal was saved changes what is owed.
    saved = {f: doc.get(f) for f in RENEWAL_INPUT_FIELDS}
    values = _validated_terms(doc, saved)
    if (flt(values["renewal_outstanding_principal"], 2) != flt(doc.renewal_outstanding_principal, 2)
            or flt(values["renewal_unpaid_interest"], 2) != flt(doc.renewal_unpaid_interest, 2)):
        raise frappe.ValidationError(
            "The amounts owed have changed since this renewal was saved. Open it, check the figures and save again."
        )

    settings = accounting.get_accounting_settings()
    # 1. Book the interest of every unpaid row that is still Pending (the interest of each row was fixed when
    #    the contract started). A row not yet due (mid-contract renewal) is booked on the effective date.
    effective = getdate(values["renewal_effective_date"])
    for row in current_schedule(doc):
        if row.status == ROW_STATUS_PENDING:
            accounting.accrue_row(doc, row, settings, min(getdate(row.payment_date), effective))

    # 2. One Journal Entry for the renewal.
    lines = _renewal_journal_lines(values, settings)
    entry = None
    if any(flt(l.get("debit")) or flt(l.get("credit")) for l in lines):
        entry = accounting._make_journal_entry(
            settings, doc.investor, values["renewal_effective_date"],
            f"Renewal ({values['renewal_structure']}) of Investor Flow {doc.name}", lines,
        )

    # 3. The renewed schedule becomes the next version; the old one stays in the history.
    current = current_schedule(doc)
    version = schedule_version(current[0]) + 1
    today = getdate(nowdate())
    for row in _schedule_rows(values):
        doc.append(SCHEDULE_TABLE_FIELD, {**row, "version": version, "version_change_date": today})

    doc.renewal_journal_entry = entry
    doc.renewal_status = RENEWAL_STATUS_APPROVED
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return get_renewal_by_id(doc.name)


def _same_rows(rows, expected: List[Dict[str, Any]]) -> bool:
    def key(r):
        return (str(getdate(r.get("payment_date"))), flt(r.get("principal_amount"), 2),
                flt(r.get("interest_amount"), 2), flt(r.get("penalty_amount"), 2))
    return sorted(key(r) for r in rows) == sorted(key(r) for r in expected)


def cancel_renewal(investor_flow_id: str) -> Dict[str, Any]:
    doc = _get_renewal_doc(investor_flow_id)
    if doc.renewal_status != RENEWAL_STATUS_APPROVED:
        raise frappe.ValidationError(f"Only an Approved renewal can be cancelled (this one is {doc.renewal_status}).")

    current = current_schedule(doc)
    values = {f: doc.get(f) for f in RENEWAL_ALL_FIELDS}
    if not _same_rows(current, _schedule_rows(values)):
        raise frappe.ValidationError(
            "The renewed schedule has been changed since the renewal was approved; the renewal cannot be cancelled."
        )
    used = [r for r in current if r.status == ROW_STATUS_PAID or r.accrual_entry or r.payout_entry]
    if used:
        raise frappe.ValidationError(
            "Part of the renewed schedule has already been accrued or paid; the renewal cannot be cancelled."
        )

    version = schedule_version(current[0])
    previous = [r for r in doc.get(SCHEDULE_TABLE_FIELD) if schedule_version(r) == version - 1]
    if not previous:
        raise frappe.ValidationError("The schedule in force before the renewal was not found.")

    accounting.cancel_journal_entry(doc.renewal_journal_entry)

    # Rows that were not yet due were booked by the approval (mid-contract renewal): undo that booking.
    effective = getdate(doc.renewal_effective_date)
    for row in previous:
        if row.status == ROW_STATUS_ACCRUED and row.accrual_entry and getdate(row.payment_date) > effective:
            accounting.cancel_journal_entry(row.accrual_entry)
            row.status = ROW_STATUS_PENDING
            row.accrual_entry = None

    # The schedule in force before the renewal comes back as the next version.
    today = getdate(nowdate())
    for row in sorted(previous, key=lambda r: r.idx):
        doc.append(SCHEDULE_TABLE_FIELD, {
            **{f: row.get(f) for f in EARNING_SCHEDULE_ROW_FIELDS + EARNING_SCHEDULE_ROW_READ_ONLY_FIELDS},
            "version": version + 1,
            "version_change_date": today,
        })

    doc.renewal_status = RENEWAL_STATUS_CANCELLED
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return get_renewal_by_id(doc.name)


def save_renewal_contract(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """After the renewal contract is emailed: saves To / Subject / Message, attaches the file, status Sent."""
    from frappe.utils import validate_email_address

    doc = _get_renewal_doc(investor_flow_id)
    if doc.renewal_status == RENEWAL_STATUS_CANCELLED:
        raise frappe.ValidationError("This renewal is Cancelled.")
    if doc.get("renewal_contract_status") == CONTRACT_STATUS_PAID:
        raise frappe.ValidationError("The renewal contract is already Paid. It cannot be changed.")

    missing = [f for f in ("to", "subject", "message", "file_id") if not data.get(f)]
    if missing:
        raise frappe.ValidationError(f"Missing required field(s): {', '.join(missing)}")
    to = str(data.get("to")).strip()
    validate_email_address(to, throw=True)

    file_doc = frappe.db.get_value(
        "File", data.get("file_id"), ["name", "file_url", "attached_to_doctype", "attached_to_name"], as_dict=True
    )
    if not file_doc:
        raise frappe.DoesNotExistError(f"File '{data.get('file_id')}' does not exist.")
    here = file_doc.attached_to_doctype == DOCTYPE and file_doc.attached_to_name == doc.name
    if file_doc.attached_to_doctype and not here:
        raise frappe.ValidationError(f"File '{file_doc.name}' is already attached to another document.")
    if not here:
        frappe.db.set_value("File", file_doc.name, {"attached_to_doctype": DOCTYPE, "attached_to_name": doc.name})

    doc.renewal_to = to
    doc.renewal_subject = data.get("subject")
    doc.renewal_message = data.get("message")
    doc.renewal_contract_status = CONTRACT_STATUS_SENT
    doc.save(ignore_permissions=True)
    return {**get_renewal_by_id(doc.name), "file_id": file_doc.name, "file_url": file_doc.file_url}
