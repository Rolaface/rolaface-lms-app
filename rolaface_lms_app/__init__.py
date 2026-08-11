__version__ = "0.0.1"

import lending.loan_management.doctype.loan_security_assignment.loan_security_assignment as lsa_module

from rolaface_lms_app.overrides.maximum_loan_amount_against_collateral_patch import patched_update_loan

lsa_module.update_loan = patched_update_loan