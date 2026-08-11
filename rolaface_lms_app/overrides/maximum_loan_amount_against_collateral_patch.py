import frappe
from frappe.utils import flt, cint

def patched_update_loan(loan, maximum_value_against_pledge, cancel=0):
    """
    Idempotent aggregation of Loan Security Assignments.
    Fully compatible with Frappe v16 strict ORM aggregation rules.
    """
    precision = cint(frappe.db.get_default("currency_precision")) or 2
    
    # 1. Idempotent Ledger Calculation (Using parameterized raw SQL to bypass ORM strictness)
    result = frappe.db.sql("""
        SELECT SUM(maximum_loan_value) 
        FROM `tabLoan Security Assignment` 
        WHERE loan = %s AND docstatus = 1
    """, (loan,))
    
    # Extract the sum (if result is None or fetch returns (None,), default to 0.0)
    total_collateral_value = result[0][0] if result and result[0][0] else 0.0
    total_collateral_value = flt(total_collateral_value, precision)
    
    # 2. Determine Loan Security State
    is_secured_loan = 1 if total_collateral_value > 0 else 0
    
    # 3. Product Default Fallback
    # If all collaterals are cancelled, the loan reverts to an unsecured state.
    # We must reset its ceiling back to the underlying Loan Product's limit.
    if is_secured_loan == 0:
        loan_product = frappe.db.get_value("Loan", loan, "loan_product")
        if loan_product:
            product_limit = frappe.db.get_value("Loan Product", loan_product, "maximum_loan_amount")
            total_collateral_value = flt(product_limit, precision)

    # 4. Atomic Database Execution
    frappe.db.sql(
        """ UPDATE `tabLoan` 
            SET maximum_loan_amount=%s, is_secured_loan=%s
            WHERE name=%s""",
        (total_collateral_value, is_secured_loan, loan),
    )