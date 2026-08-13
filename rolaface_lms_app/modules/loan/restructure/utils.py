from frappe.utils import add_months, add_days, getdate
import frappe

def create_search_filters(search):
    return [
                   ["name", "like", f"%{search}%"],
                   ["applicant_type", "like", f"%{search}%"],
                   ["applicant", "like", f"%{search}%"],
                   ["loan", "like", f"%{search}%"],
                   ["loan_product", "like", f"%{search}%"]
               ]



def _add_periods(start_date, periods, frequency):

    if not start_date or periods is None:
        return None

    start_date = getdate(start_date)
    periods = int(periods)
    frequency = (frequency or "").strip().lower()

    if frequency in ("monthly",):
        return add_months(start_date, periods)
    if frequency in ("weekly",):
        return add_days(start_date, periods * 7)
    if frequency in ("bi-weekly", "biweekly", "fortnightly"):
        return add_days(start_date, periods * 14)
    if frequency in ("daily",):
        return add_days(start_date, periods)

    frappe.throw(f"Unsupported repayment frequency: '{frequency}'")
