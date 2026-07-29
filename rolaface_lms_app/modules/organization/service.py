import frappe
from .utils.utils import (
    build_company_response,
    map_company_update_fields,
)
from mimetypes import guess_type
from frappe.utils.image import optimize_image
from frappe.utils import cint
from .utils.term_utils import sync_company_terms


def get_company_details():

    company_name = frappe.defaults.get_user_default("Company")

    if not company_name:
        frappe.throw("No default company set")

    company = frappe.get_doc("Company", company_name)

    return build_company_response(company)


def update_company_details(data):
    company_name = frappe.defaults.get_user_default("Company")

    if not company_name:
        frappe.throw("No default company set")

    company = frappe.get_doc("Company", company_name)

    map_company_update_fields(company, data)
    save_company_terms(company, data)

    company.save(ignore_permissions=False)
    frappe.db.commit()

    return company.name


def remove_attach(doctype, docname, fieldname):
    old_file = frappe.get_value(
        "File",
        {
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "attached_to_field": fieldname,
        },
        "name",
    )

    if old_file:
        frappe.delete_doc("File", old_file, ignore_permissions=True)


def upload_file(
    file, doctype, docname, fieldname, folder="Home", is_private=0, optimize=True
):

    content = file.stream.read()
    filename = file.filename

    content_type = guess_type(filename)[0]
    if optimize and content_type and content_type.startswith("image/"):
        args = {"content": content, "content_type": content_type}
        if frappe.form_dict.max_width:
            args["max_width"] = int(frappe.form_dict.max_width)
        if frappe.form_dict.max_height:
            args["max_height"] = int(frappe.form_dict.max_height)
        content = optimize_image(**args)

    frappe.local.uploaded_file = content
    frappe.local.uploaded_filename = filename

    return frappe.get_doc(
        {
            "doctype": "File",
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "attached_to_field": fieldname,
            "folder": folder,
            "file_name": filename,
            "is_private": cint(is_private),
            "content": content,
        }
    ).save(ignore_permissions=True)


def save_company_terms(company, data):
    company_name = frappe.defaults.get_user_default("Company")

    if not company_name:
        frappe.throw("No default company set")

    terms_data = data.get("terms")
    if not terms_data:
        frappe.throw("No terms data provided")

    result = sync_company_terms(company, terms_data)
    frappe.db.commit()

    return result


COMPANY_DEFAULT_FIELDS = [
    # Basic Info
    "company_name",
    "abbr",
    "default_currency",
    # Payroll
    "default_payroll_payable_account",
    "default_employee_advance_account",
    # Accounts
    "default_bank_account",
    "default_cash_account",
    "default_receivable_account",
    "default_payable_account",
    "default_expense_account",
    "default_income_account",
    "round_off_account",
    "round_off_cost_center",
    "write_off_account",
    "exchange_gain_loss_account",
    "unrealized_exchange_gain_loss_account",
    "default_deferred_revenue_account",
    "default_deferred_expense_account",
    "default_advance_received_account",
    "default_advance_paid_account",
    # Cost Center & Finance
    "cost_center",
    "default_finance_book",
    # HR & Leave
    "default_holiday_list",
    # Selling / Buying
    "default_selling_terms",
    "default_buying_terms",
    "default_in_transit_warehouse",
]


def get_company_defaults_data():
    company = frappe.defaults.get_user_default("Company")

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    if not company:
        frappe.throw("No default company found for the current user.")

    data = frappe.db.get_value(
        "Company",
        company,
        COMPANY_DEFAULT_FIELDS,
        as_dict=True,
    )

    if not data:
        frappe.throw(f"Company '{company}' does not exist.")

    company_doc = frappe.get_doc("Company", company)

    # extended_details = (
    #     company_doc.custom_extended_details[0]
    #     if company_doc.custom_extended_details
    #     else None
    # )

    # data["primary_business_domain"] = (
    #     extended_details.primary_business_domain if extended_details else None
    # )

    # data["default_payment_mode"] = (
    #     extended_details.default_payment_mode if extended_details else None
    # )
    # data["use_separate_sequence_for_credit_notes"] = extended_details.use_separate_sequence_for_credit_notes if extended_details else None

    data["credit_controller"] = frappe.db.get_single_value("Accounts Settings", "credit_controller")

    return data


def update_company_defaults_data(data):
    company = frappe.defaults.get_user_default("Company")

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    if not company:
        frappe.throw("No default company found for the current user.")

    company_doc = frappe.get_doc("Company", company)

    for field in COMPANY_DEFAULT_FIELDS:
        if field in data:
            company_doc.set(field, data.get(field))

    # if not company_doc.custom_extended_details:
    #     company_doc.append("custom_extended_details", {})

    # extended_details = company_doc.custom_extended_details[0]

    # if "primary_business_domain" in data:
    #     extended_details.primary_business_domain = data.get("primary_business_domain")

    # if "default_payment_mode" in data:
    #     extended_details.default_payment_mode = data.get("default_payment_mode")

    # if "use_separate_sequence_for_credit_notes" in data:
    #     extended_details.use_separate_sequence_for_credit_notes = int(data.get("use_separate_sequence_for_credit_notes", False))

    company_doc.save()

    if "credit_controller" in data:
        role = data.get("credit_controller")
        if role and not frappe.db.exists("Role", role):
            frappe.throw(f"Role '{role}' does not exist.")
        
        frappe.db.set_single_value("Accounts Settings", "credit_controller", role or "")

    frappe.db.commit()

    result = frappe.db.get_value(
        "Company",
        company_doc.name,
        COMPANY_DEFAULT_FIELDS,
        as_dict=True,
    )

    # result["primary_business_domain"] = extended_details.primary_business_domain
    # result["default_payment_mode"] = extended_details.default_payment_mode
    # result["use_separate_sequence_for_credit_notes"] = extended_details.use_separate_sequence_for_credit_notes
    result["credit_controller"] = frappe.db.get_single_value("Accounts Settings", "credit_controller")

    return result


COMPANY_LENDING_SETUP_FIELDS = [
    # Basic Company
    "company_name",
    "abbr",
    "default_currency",

    # Loan Settings
    "loan_restructure_limit",
    "watch_period_post_loan_restructure_in_days",
    "interest_day_count_convention",
    "min_days_bw_disbursement_first_repayment",
    "loan_accrual_frequency",

    # Loan Accounting
    "enable_loan_accounting",
    "enable_async_gl_reversal",
    "async_gl_reversal_start_date",

    # Collection Settings
    "collection_offset_logic_based_on",
    "days_past_due_threshold",
    "days_past_due_threshold_for_auto_write_off",

    # Collection Offset Sequences
    "collection_offset_sequence_for_sub_standard_asset",
    "collection_offset_sequence_for_standard_asset",
    "collection_offset_sequence_for_written_off_asset",
    "collection_offset_sequence_for_settlement_collection",
]
def get_company_lending_setup():
    company = frappe.defaults.get_user_default("Company")

    if not company:
        company = frappe.db.get_single_value(
            "Global Defaults",
            "default_company",
        )

    if not company:
        frappe.throw("No default company found.")

    data = frappe.db.get_value(
        "Company",
        company,
        COMPANY_LENDING_SETUP_FIELDS,
        as_dict=True,
    )

    if not data:
        frappe.throw(f"Company '{company}' does not exist.")

    return data

def update_company_lending_setup(data):
    company = frappe.defaults.get_user_default("Company")

    if not company:
        company = frappe.db.get_single_value(
            "Global Defaults",
            "default_company",
        )

    if not company:
        frappe.throw("No default company found.")

    company_doc = frappe.get_doc("Company", company)

    for field in COMPANY_LENDING_SETUP_FIELDS:
        if field in data:
            company_doc.set(field, data.get(field))

    company_doc.save()
    frappe.db.commit()

    return frappe.db.get_value(
        "Company",
        company,
        COMPANY_LENDING_SETUP_FIELDS,
        as_dict=True,
    )