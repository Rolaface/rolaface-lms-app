from dateutil.relativedelta import relativedelta
from frappe.utils.data import add_days, add_months
from lending.loan_management.doctype.loan_repayment_schedule.utils import add_single_month
from datetime import date

def get_amounts(balance_amount, rate_of_interest, days, months, monthly_repayment_amount ):

    current_balance_amount = balance_amount

    interest_amount = round(current_balance_amount * float(rate_of_interest) * days / (months * 100), 2)

    principal_amount = monthly_repayment_amount - float(interest_amount)

    if interest_amount > monthly_repayment_amount:
        interest_amount = monthly_repayment_amount
        principal_amount = 0

    balance_amount = round(balance_amount + interest_amount - monthly_repayment_amount, 2)

    if balance_amount < 0:
        principal_amount += balance_amount
        balance_amount = 0.0

    total_payment = principal_amount + interest_amount

    return (interest_amount, principal_amount, balance_amount, total_payment, days)

def get_period_days(payment_date: date, repayment_frequency: str) -> int:
    """Days used in the interest formula for this period. See assumption #1/#2 above."""
    if repayment_frequency == "Monthly":
        prev = payment_date - relativedelta(months=1)
        return (payment_date - prev).days
    return {
        "Bi-Weekly": 14,
        "Weekly": 7,
        "Daily": 1,
        "Quarterly": 3,
    }[repayment_frequency]

def get_next_payment_date(payment_date: date, repayment_frequency: str) -> date:
    if repayment_frequency == "Monthly":
        return add_single_month(payment_date)
    elif repayment_frequency == "Bi-Weekly":
        return add_days(payment_date, 14)
    elif repayment_frequency == "Weekly":
        return add_days(payment_date, 7)
    elif repayment_frequency == "Daily":
        return add_days(payment_date, 1)
    elif repayment_frequency == "Quarterly":
        return add_months(payment_date, 3)
    raise ValueError(f"Unsupported repayment_frequency '{repayment_frequency}'")
