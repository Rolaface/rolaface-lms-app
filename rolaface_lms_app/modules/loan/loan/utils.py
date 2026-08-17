import frappe
from frappe.utils import flt
from typing import Dict, Any
import json


def validate_loan_payload(data: Dict[str, Any], is_update=False):
    if not is_update:
        required_fields = [
            "applicant_type",
            "applicant",
            "loan_product",
            "company",
            "loan_amount",
        ]
        for field in required_fields:
            if not data.get(field):
                raise frappe.ValidationError(f"'{field}' is required.")

    if not data.get("maximum_loan_amount") and data.get("loan_amount"):
        data["maximum_loan_amount"] = data.get("loan_amount")

    numeric_fields = ["loan_amount", "rate_of_interest", "repayment_periods"]
    for field in numeric_fields:
        if field in data and flt(data.get(field)) < 0:
            raise frappe.ValidationError(f"'{field}' cannot be negative.")

    if data.get("company") and not frappe.db.exists("Company", data.get("company")):
        raise frappe.ValidationError(f"Company '{data.get('company')}' does not exist.")

    if data.get("loan_product") and not frappe.db.exists(
        "Loan Product", data.get("loan_product")
    ):
        raise frappe.ValidationError(
            f"Loan Product '{data.get('loan_product')}' does not exist."
        )

    charges = data.get("loan_charges")
    if charges:
        if not isinstance(charges, list):
            raise frappe.ValidationError("'loan_charges' must be an array.")

        valid_treatments = ["Billed Separately", "Add to first repayment"]

        for idx, charge in enumerate(charges):
            if not charge.get("charge"):
                raise frappe.ValidationError(
                    f"Row {idx+1} in loan_charges: 'charge' is required."
                )

            amt = flt(charge.get("amount"))
            if amt < 0:
                raise frappe.ValidationError(
                    f"Row {idx+1} in loan_charges: Amount cannot be negative."
                )

            if charge.get("account") and not frappe.db.exists(
                "Account", charge.get("account")
            ):
                raise frappe.ValidationError(
                    f"Row {idx+1} in loan_charges: Account '{charge.get('account')}' does not exist."
                )

            treatment = charge.get("treatment_of_charge")
            if treatment and treatment not in valid_treatments:
                raise frappe.ValidationError(
                    f"Row {idx+1} in loan_charges: 'treatment_of_charge' must be one of {valid_treatments}."
                )

    collaterals = data.get("collaterals")

    if collaterals:
        if not isinstance(collaterals, dict):
            raise frappe.ValidationError("'collaterals' must be an object.")

        items = collaterals.get("items")

        if not isinstance(items, list) or len(items) == 0:
            raise frappe.ValidationError(
                "At least one item is required inside 'collaterals.items'."
            )

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise frappe.ValidationError(
                    f"Row {idx + 1} in collaterals must be an object."
                )

            if not item.get("loan_security"):
                raise frappe.ValidationError(
                    f"Row {idx + 1} in collaterals: 'loan_security' is required."
                )

            qty = flt(item.get("qty"))
            if qty <= 0:
                raise frappe.ValidationError(
                    f"Row {idx + 1} in collaterals: 'qty' must be greater than zero."
                )

            price = flt(item.get("loan_security_price"))
            if price <= 0:
                raise frappe.ValidationError(
                    f"Row {idx + 1} in collaterals: 'loan_security_price' must be greater than zero."
                )

            if not frappe.db.exists("Loan Security", item.get("loan_security")):
                raise frappe.ValidationError(
                    f"Loan Security '{item.get('loan_security')}' does not exist."
                )

    account_fields = [
        "disbursement_account",
        "payment_account",
        "loan_account",
        "interest_income_account",
        "penalty_income_account",
    ]
    for acc_field in account_fields:
        acc = data.get(acc_field)
        if acc and not frappe.db.exists("Account", acc):
            raise frappe.ValidationError(
                f"Account '{acc}' provided for {acc_field} does not exist."
            )


def build_loan_filters(args: Dict[str, Any]) -> Dict[str, Any]:
    frappe_filters = {}
    if not args:
        return frappe_filters

    if args.get("company"):
        frappe_filters["company"] = args["company"]

    if args.get("status"):
        status = args["status"]

        if isinstance(status, str):
            try:
                status = json.loads(status)
            except json.JSONDecodeError:
                status = [status]
        frappe_filters["status"] = (
                                    ["in", status]
                                    if isinstance(status, list)
                                    else status
                                )

    if args.get("applicant"):
        frappe_filters["applicant"] = args["applicant"]

    if args.get("loan_product"):
        loan_product = args.get("loan_product")
        if isinstance(loan_product, str):
            try:
                loan_product = json.loads(loan_product)
            except json.JSONDecodeError:
                loan_product = [loan_product]

        frappe_filters["loan_product"] = ["in",loan_product]

    minAmount = args.get("minAmount")
    maxAmount = args.get("maxAmount")
    if minAmount and maxAmount:
        frappe_filters["loan_amount"] = ["between", [flt(minAmount), flt(maxAmount)]]
    elif minAmount:
        frappe_filters["loan_amount"] = [">=", flt(minAmount)]
    elif maxAmount:
        frappe_filters["loan_amount"] = ["<=", flt(maxAmount)]

    return frappe_filters


def sync_loan_charges(loan_doc, charges_payload: list) -> bool:
    if charges_payload is None:
        return False

    loan_doc.set("loan_charges", [])

    for charge in charges_payload:
        loan_doc.append(
            "loan_charges",
            {
                "charge": charge.get("charge"),
                "amount": flt(charge.get("amount")),
                "account": charge.get("account"),
                "treatment_of_charge": charge.get("treatment_of_charge"),
            },
        )
    return True

def sync_loan_documents(loan_id: str, documents_payload: list):
    if not documents_payload:
        raise frappe.ValidationError("'documents' array is required.")

    attached = []
    for idx, doc in enumerate(documents_payload):
        file_url = doc.get("file_url")
        if not file_url:
            raise frappe.ValidationError(f"Row {idx+1}: 'file_url' is required.")

        file_name = doc.get("file_name") or file_url.split("/")[-1]

        existing_file = frappe.db.get_value(
            "File",
            {
                "file_url": file_url,
                "attached_to_doctype": "Loan",
                "attached_to_name": loan_id,
            },
            "name",
        )

        if existing_file:
            attached.append(existing_file)
            continue

        # Otherwise check if it's a "loose" file not attached to anything yet
        loose_file = frappe.db.get_value(
            "File",
            {"file_url": file_url, "attached_to_name": ["in", ["", None]]},
            "name",
        )

        if loose_file:
            frappe.db.set_value(
                "File",
                loose_file,
                {"attached_to_doctype": "Loan", "attached_to_name": loan_id},
            )
            attached.append(loose_file)
        else:
            source_is_private = frappe.db.get_value(
                "File", {"file_url": file_url}, "is_private"
            )
            if source_is_private is None:
                source_is_private = doc.get("is_private", 1)

            new_file = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": file_name,
                    "file_url": file_url,
                    "attached_to_doctype": "Loan",
                    "attached_to_name": loan_id,
                    "is_private": source_is_private,
                }
            )
            new_file.insert(ignore_permissions=True)
            attached.append(new_file.name)

    return attached