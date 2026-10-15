"""
Amend Payouts: changes to an investment's repayment schedule, made as amendments.

An amendment is a schedule version whose rows carry amend_status (Custom Investor Earning Schedule):
  Draft     - saved, not in use (payouts, reports and Investor 360 keep using the schedule in use);
              one Draft per investment; can be edited or deleted.
  Approved  - the edits are applied to the schedule in use at that moment (same checks as editing the
              schedule: Paid rows locked, Accrued / Partially Paid rows keep date, principal and interest) and
              saved as the new schedule version in use.
  Cancelled - an Approved amendment taken back: the schedule in use goes back to the version before it.
              Allowed only while it is still the schedule in use and none of its EMIs has been paid since.
              A Cancelled amendment can be deleted.

A Draft keeps every row of the schedule it was made from, in order; on Approve its rows are matched with the
rows of the schedule in use by position (the schedule in use must still have the same number of rows).
"""
import frappe
from typing import Any, Dict, List, Optional, Tuple
from frappe.utils import flt, getdate

from .constant import (
    DOCTYPE,
    SCHEDULE_TABLE_FIELD,
    EARNING_FUND_STATUSES,
    EARNING_SCHEDULE_ROW_FIELDS,
)
from .utils import (
    AMEND_APPROVED,
    AMEND_CANCELLED,
    AMEND_DRAFT,
    AMEND_STATUS_FIELD,
    _as_list,
    current_schedule,
    in_use,
    schedule_version,
)
from . import service

SCHEDULE_DOCTYPE = "Custom Investor Earning Schedule"


def _doc(investor_flow_id: str, for_update: bool = False):
    return service._get_earning_doc(investor_flow_id, for_update=for_update)


def _rows_of(doc, version: int) -> List:
    """Rows of one amendment (version with an amend status), in order."""
    rows = [
        r for r in doc.get(SCHEDULE_TABLE_FIELD) or []
        if schedule_version(r) == version and r.get(AMEND_STATUS_FIELD)
    ]
    if not rows:
        raise frappe.DoesNotExistError(f"Amendment version {version} is not on Investor Flow '{doc.name}'.")
    return sorted(rows, key=lambda r: r.idx)


def _status_of(rows) -> str:
    return rows[0].get(AMEND_STATUS_FIELD)


def _draft_version(doc) -> Optional[int]:
    versions = {schedule_version(r) for r in doc.get(SCHEDULE_TABLE_FIELD) or [] if r.get(AMEND_STATUS_FIELD) == AMEND_DRAFT}
    return max(versions) if versions else None


def _amendment(doc, version: int) -> Dict[str, Any]:
    """The amendment in the shape of a Repayment Record (so the schedule screen can show it)."""
    rows = _rows_of(doc, version)
    result = service.get_investor_earning_by_id(doc.name)
    result.update({
        "schedule_version": version,
        SCHEDULE_TABLE_FIELD: [service._schedule_row_dict(row, i) for i, row in enumerate(rows, start=1)],
        "amend_status": _status_of(rows),
        # Totals of the schedule in use: an amendment cannot go above them (checked on the screen).
        "in_use_totals": {
            f: flt(sum(flt(r.get(f)) for r in current_schedule(doc)), 2)
            for f in ("principal_amount", "interest_amount")
        },
        "amend_date": str(rows[0].get("version_change_date")) if rows[0].get("version_change_date") else None,
    })
    return result


def _payload_for_current(doc, version: int, edits: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """The amendment's rows (or the screen's edits of them) as edits of the schedule in use, matched by position."""
    draft = _rows_of(doc, version)
    current = current_schedule(doc)
    if len(draft) != len(current):
        raise frappe.ValidationError(
            f"The schedule in use has changed since this amendment was saved ({len(current)} rows now, "
            f"{len(draft)} in the amendment). Delete it and create a new amendment."
        )
    by_name = {e.get("name"): e for e in (edits or [])}
    rows = []
    for d, c in zip(draft, current):
        source = by_name.get(d.name) or {}
        rows.append({"name": c.name, **{f: source.get(f, d.get(f)) for f in EARNING_SCHEDULE_ROW_FIELDS}})
    return {SCHEDULE_TABLE_FIELD: rows}


def _remove_rows(doc, rows):
    for r in rows:
        doc.remove(r)


# --------------------------------- List / pick ---------------------------------

def get_amendments(args: Dict[str, Any], page: int, page_size: int) -> Tuple[list, int, int]:
    """Every amendment (one row per investment and version), newest first."""
    filters = {"parenttype": DOCTYPE, "parentfield": SCHEDULE_TABLE_FIELD, AMEND_STATUS_FIELD: ["is", "set"]}
    statuses = [s for s in _as_list(args.get("amend_status")) if s] if args.get("amend_status") else []
    if statuses:
        filters[AMEND_STATUS_FIELD] = ["in", statuses]
    search = (args.get("search") or "").strip()
    if search:
        term = f"%{search}%"
        investor_ids = service._matching_investors(term)
        parents = frappe.get_all(
            DOCTYPE,
            or_filters=[["name", "like", term]] + ([["investor", "in", investor_ids]] if investor_ids else []),
            pluck="name",
        )
        filters["parent"] = ["in", parents or [""]]

    rows = frappe.get_all(
        SCHEDULE_DOCTYPE,
        filters=filters,
        fields=["parent", "version", AMEND_STATUS_FIELD, "version_change_date", "modified",
                "principal_amount", "interest_amount", "penalty_amount", "total_payment"],
        parent_doctype=DOCTYPE,
    )
    groups: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for r in rows:
        key = (r.parent, schedule_version(r))
        g = groups.setdefault(key, {
            "investment_id": r.parent,
            "version": key[1],
            "amend_status": r.get(AMEND_STATUS_FIELD),
            "amend_date": str(r.version_change_date) if r.version_change_date else None,
            "modified": r.modified,
            "emis": 0,
            "principal": 0.0, "interest": 0.0, "penalty": 0.0, "total": 0.0,
        })
        g["emis"] += 1
        g["principal"] += flt(r.principal_amount)
        g["interest"] += flt(r.interest_amount)
        g["penalty"] += flt(r.penalty_amount)
        g["total"] += flt(r.total_payment)
        g["modified"] = max(g["modified"], r.modified)

    result = sorted(groups.values(), key=lambda g: g["modified"], reverse=True)
    investors = dict(frappe.get_all(
        DOCTYPE, filters={"name": ["in", list({g["investment_id"] for g in result})]},
        fields=["name", "investor"], as_list=True,
    )) if result else {}
    names = service._get_names("Customer", "customer_name", list(investors.values()))
    for g in result:
        for f in ("principal", "interest", "penalty", "total"):
            g[f] = flt(g[f], 2)
        g["investor_id"] = investors.get(g["investment_id"])
        g["investor"] = names.get(g["investor_id"]) or g["investor_id"]
        g["modified"] = str(g["modified"])

    total = len(result)
    total_pages = max((total + page_size - 1) // page_size, 1)
    return result[(page - 1) * page_size: page * page_size], total, total_pages


def get_amend_candidates(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Investments whose schedule can be amended now (funded, not Cancelled / Matured, not fully paid or
    expired, no Draft amendment yet), by investment ID or investor name / mobile / ID / email."""
    filters = {"fund_status": ["in", EARNING_FUND_STATUSES], "status": ["not in", ["Cancelled", "Matured"]]}
    or_filters = None
    if search:
        term = f"%{str(search).strip()}%"
        or_filters = [["name", "like", term], ["investor", "like", term]]
        investor_ids = service._matching_investors(term)
        if investor_ids:
            or_filters.append(["investor", "in", investor_ids])
    names = frappe.get_all(DOCTYPE, filters=filters, or_filters=or_filters, pluck="name", order_by="modified desc", limit=30)

    from .renewal import is_expired
    result = []
    for name in names:
        doc = frappe.get_doc(DOCTYPE, name)
        current = current_schedule(doc)
        if not current or _draft_version(doc) or is_expired(doc) or all(r.status == "Paid" for r in current):
            continue
        customer = frappe.db.get_value("Customer", doc.investor, ["customer_name", "email_id", "mobile_no"], as_dict=True) or {}
        result.append({
            "id": doc.name,
            "investor_id": doc.investor,
            "investor": customer.get("customer_name") or doc.investor,
            "investor_email": customer.get("email_id"),
            "investor_mobile": customer.get("mobile_no"),
            "emis": len(current),
            "emis_paid": len([r for r in current if r.status == "Paid"]),
        })
    return result


# --------------------------------- One amendment ---------------------------------

def get_amendment(investor_flow_id: str, version: Optional[int] = None) -> Dict[str, Any]:
    """An amendment; without a version, the schedule in use to start a new amendment from."""
    doc = _doc(investor_flow_id)
    if version:
        return _amendment(doc, int(version))
    draft = _draft_version(doc)
    if draft:
        raise frappe.ValidationError(
            f"Investment {doc.name} already has a Draft amendment (version {draft}); edit that one instead."
        )
    return service.get_investor_earning_by_id(doc.name)


def create_amendment(investor_flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Saves the edits of the schedule in use as a Draft amendment (not in use until approved)."""
    doc = _doc(investor_flow_id, for_update=True)
    draft = _draft_version(doc)
    if draft:
        raise frappe.ValidationError(
            f"Investment {doc.name} already has a Draft amendment (version {draft}); edit that one instead."
        )
    current, new_values, any_change = service.edited_schedule(doc, data)
    if not any_change:
        raise frappe.ValidationError("Nothing is changed from the schedule in use; change at least one row.")
    version = service.append_schedule_version(doc, current, new_values, AMEND_DRAFT)
    doc.save(ignore_permissions=True)
    return _amendment(doc, version)


def update_amendment(investor_flow_id: str, version: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Edits a Draft amendment (data["schedule"]: its rows by name)."""
    doc = _doc(investor_flow_id, for_update=True)
    version = int(version)
    draft = _rows_of(doc, version)
    if _status_of(draft) != AMEND_DRAFT:
        raise frappe.ValidationError("Only a Draft amendment can be edited.")
    payload = _payload_for_current(doc, version, data.get(SCHEDULE_TABLE_FIELD) or [])
    current, new_values, any_change = service.edited_schedule(doc, payload)
    if not any_change:
        raise frappe.ValidationError("Nothing is changed from the schedule in use; change at least one row.")
    for d, c in zip(draft, current):
        for f in EARNING_SCHEDULE_ROW_FIELDS:
            d.set(f, new_values[c.name][f])
    doc.save(ignore_permissions=True)
    return _amendment(doc, version)


def delete_amendment(investor_flow_id: str, version: int):
    doc = _doc(investor_flow_id, for_update=True)
    rows = _rows_of(doc, int(version))
    if _status_of(rows) not in (AMEND_DRAFT, AMEND_CANCELLED):
        raise frappe.ValidationError("Only a Draft or Cancelled amendment can be deleted.")
    _remove_rows(doc, rows)
    doc.save(ignore_permissions=True)


def approve_amendment(investor_flow_id: str, version: int) -> Dict[str, Any]:
    """Applies a Draft amendment to the schedule in use; it becomes the schedule in use (Approved)."""
    doc = _doc(investor_flow_id, for_update=True)
    version = int(version)
    draft = _rows_of(doc, version)
    if _status_of(draft) != AMEND_DRAFT:
        raise frappe.ValidationError("Only a Draft amendment can be approved.")
    # Checked again against the schedule in use now (a payout may have paid some EMIs since it was saved).
    payload = _payload_for_current(doc, version)
    current, new_values, any_change = service.edited_schedule(doc, payload)
    if not any_change:
        raise frappe.ValidationError("This amendment no longer changes anything in the schedule in use.")
    _remove_rows(doc, draft)
    approved = service.append_schedule_version(doc, current, new_values, AMEND_APPROVED)
    from .renewal import refresh_payment_status
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return _amendment(doc, approved)


def cancel_amendment(investor_flow_id: str, version: int) -> Dict[str, Any]:
    """Takes back an Approved amendment: the schedule in use goes back to the version before it."""
    doc = _doc(investor_flow_id, for_update=True)
    version = int(version)
    rows = _rows_of(doc, version)
    if _status_of(rows) != AMEND_APPROVED:
        raise frappe.ValidationError("Only an Approved amendment can be cancelled.")
    current = current_schedule(doc)
    if not current or schedule_version(current[0]) != version:
        raise frappe.ValidationError(
            "A later schedule is in use (another amendment or a Fund Receipt changed it); "
            "this amendment can no longer be cancelled."
        )
    earlier = [r for r in doc.get(SCHEDULE_TABLE_FIELD) or [] if in_use(r) and schedule_version(r) < version]
    if not earlier:
        raise frappe.ValidationError("There is no earlier schedule to go back to.")
    previous_version = max(schedule_version(r) for r in earlier)
    previous = sorted((r for r in earlier if schedule_version(r) == previous_version), key=lambda r: r.idx)
    # Nothing may have been paid (or booked) on its EMIs since it was approved.
    paid_fields = ("status", "paid_amount", "accrual_entry", "payout_entry")
    if len(previous) != len(rows) or any(
        (flt(a.get(f)) if f == "paid_amount" else (a.get(f) or None)) != (flt(b.get(f)) if f == "paid_amount" else (b.get(f) or None))
        for a, b in zip(rows, previous) for f in paid_fields
    ):
        raise frappe.ValidationError(
            "Payouts of this amendment have been paid since it was approved; it can no longer be cancelled."
        )
    for r in rows:
        r.set(AMEND_STATUS_FIELD, AMEND_CANCELLED)
    from .renewal import refresh_payment_status
    refresh_payment_status(doc)
    doc.save(ignore_permissions=True)
    return _amendment(doc, version)
