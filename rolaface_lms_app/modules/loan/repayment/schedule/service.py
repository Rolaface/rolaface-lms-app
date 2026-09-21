from .utils import get_amounts, get_next_payment_date, get_period_days
from frappe.utils import getdate
from datetime import date

def get_fixed_repayment_schedule(loan_amount, rate_of_interest, monthly_repayment_amount, repayment_frequency, repayment_start_date):
    payment_date = getdate(repayment_start_date) or date.today()
    months = 365

    balance_amount = loan_amount
    schedule = []

    while balance_amount > 0:
        days = get_period_days(payment_date, repayment_frequency)

        (
            interest_amount,
            principal_amount,
            balance_amount,
            total_payment,
            days,
        ) = get_amounts(
                            balance_amount,
                            rate_of_interest,
                            days, months,
                            monthly_repayment_amount,
                        )

        schedule.append(
            {
                "payment_date": payment_date,
                "principal_amount": round(principal_amount, 2),
                "interest_amount": round(interest_amount, 2),
                "total_payment": round(total_payment, 2),
                "balance_loan_amount": balance_amount,
                # "number_of_days": days,
            }
        )

        payment_date = get_next_payment_date(payment_date, repayment_frequency)

    response = {
                    "loan_amount": loan_amount,
                    "rate_of_interest": rate_of_interest,
                    "monthly_repayment_amount": monthly_repayment_amount,
                    "repayment_start_date": repayment_start_date,
                    "repayment_periods": schedule
                }
    return response
