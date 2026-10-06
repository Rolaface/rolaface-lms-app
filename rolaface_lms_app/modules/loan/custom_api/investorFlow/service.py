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
)
from .utils import _validate_investor_flow_payload, _build_investor_flow_filters
from frappe.utils import getdate, add_months, add_days, flt, nowdate


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

    amount = flt(data.get("investment_amount"))
    rate = flt(data.get("interest_rate"))
    penalty_rate = flt(data.get("penalty_rate"))
    frequency = data.get("repayment_frequency")
    first_repayment_date = getdate(data.get("first_repayment_date"))
    maturity_date = getdate(data.get("maturity_date"))
    today = getdate(nowdate())

    if first_repayment_date <= today:
        raise frappe.ValidationError("First Repayment Date must be in the future.")

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

    # Interest is split equally across the payouts; principal is returned on the last one.
    per_payment = total_interest / len(dates)
    schedule = []
    for i, date in enumerate(dates):
        principal = amount if i == len(dates) - 1 else 0
        schedule.append({
            "installment_no": i + 1,
            "date": str(date),
            "principal": flt(principal, 2),
            "interest": flt(per_payment, 2),
            "total": flt(principal + per_payment, 2),
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