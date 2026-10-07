import frappe
from rolaface_lms_app.utils.api_response import send_response, send_response_list, handle_api_error
from rolaface_lms_app.utils.api_request import parse_api_payload
from . import service, accounting, maturity


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_investor_flow():
    """
    Create Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Create a new Investor Flow (investor, product and investment terms).
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investor
              - investment_product
              - investment_amount
              - repayment_frequency
              - maturity_date
              - interest_rate
              - first_repayment_date
            properties:
              investor:
                type: string
                description: Customer ID.
              investment_product:
                type: string
                description: Custom Investment Product ID.
              investment_amount:
                type: integer
              repayment_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              maturity_date:
                type: string
                format: date
              interest_rate:
                type: number
              first_repayment_date:
                type: string
                format: date
              penalty_rate:
                type: number
    responses:
      201:
        description: Investor Flow created successfully.
    """
    try:
        data = parse_api_payload()
        result = service.create_investor_flow(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow created successfully.",
            data=result,
            status_code=201,
            http_status=201,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Create Investor Flow API Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_flow(id=None):
    """
    Update Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Update specific attributes of an Investor Flow.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    responses:
      200:
        description: Investor Flow updated successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required as a query parameter (?id=...).")

        result = service.update_investor_flow(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Flow API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_flow_by_id(id=None):
    """
    Get Investor Flow By ID
    ---
    tags:
      - Investor Flow
    summary: Fetch full details of an Investor Flow by ID.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        data = service.get_investor_flow_by_id(investor_flow_id)

        return send_response(
            status="success",
            message="Investor Flow retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Flow By ID Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_flow(page=1, page_size=20):
    """
    List Investor Flows
    ---
    tags:
      - Investor Flow
    summary: Paginated list of Investor Flows with filtering.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID, investor (Customer ID) or investment product ID.
      - in: query
        name: investor
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: investment_product
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: repayment_frequency
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: status
        schema:
          type: string
        description: A single value or a JSON array of values.
      - in: query
        name: sort_by
        schema:
          type: string
      - in: query
        name: sort_order
        schema:
          type: string
          enum: [asc, desc]
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        sort_by = args.get("sort_by", "creation")
        sort_order = args.get("sort_order", "desc")

        records, total_records, total_pages = service.get_investor_flows(
            args=args,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        response_data = {
            "success": True,
            "message": "Investor Flows retrieved successfully.",
            "data": records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success",
            message="Success",
            data=response_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get All Investor Flows Error")


@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_investor_flow(id=None):
    """
    Delete Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Delete an Investor Flow.
    parameters:
      - in: query
        name: id
        required: true
    """
    try:
        investor_flow_id = id or frappe.local.form_dict.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        service.delete_investor_flow(investor_flow_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow deleted successfully.",
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Investor Flow Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_flow_status(id=None, action=None):
    """
    Update Investor Flow Status
    ---
    tags:
      - Investor Flow
    summary: Move an Investor Flow to a new status.
    description: |
      Allowed: Draft -> Approved / Cancelled, Approved -> Cancelled.
      Received is set only by receive_payment; Matured only by close_investor_flow.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
      - in: query
        name: action
        required: true
        schema:
          type: string
          enum: [approved, cancelled]
    responses:
      200:
        description: Investor Flow status updated successfully.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        action_value = action or frappe.request.args.get("action")

        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        if not action_value:
            raise frappe.ValidationError("Action is required (approved, cancelled).")

        action_clean = str(action_value).strip().lower()

        result = service.update_investor_flow_status(investor_flow_id, action_clean)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Investor Flow {result['status']} successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Flow Status API Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_bank_accounts(investor=None):
    """
    Get Investor Bank Accounts
    ---
    tags:
      - Investor Flow
    summary: Enabled Bank Accounts with Party Type = Customer and Party = the investor (used for Paid From).
    parameters:
      - in: query
        name: investor
        required: true
        schema:
          type: string
        description: Customer ID.
    responses:
      200:
        description: Bank Accounts retrieved successfully.
    """
    try:
        investor_id = investor or frappe.request.args.get("investor")
        if not investor_id:
            raise frappe.ValidationError("Investor (Customer ID) is required.")

        data = service.get_investor_bank_accounts(investor_id)

        return send_response(
            status="success",
            message="Bank Accounts retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Bank Accounts Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def save_contract(id=None):
    """
    Save Investor Flow Contract
    ---
    tags:
      - Investor Flow
    summary: >
      After the contract is emailed (frappe.core.doctype.communication.email.make), save To, Subject and Message,
      attach the contract File to the Investor Flow and set Contract Status to Sent.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - to
              - subject
              - message
              - file_id
            properties:
              to:
                type: string
              subject:
                type: string
              message:
                type: string
                description: Email body that was sent.
              file_id:
                type: string
                description: File ID (name) of the uploaded contract PDF.
    responses:
      200:
        description: Contract saved successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = service.save_contract(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Contract saved successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Save Investor Flow Contract Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_payment(id=None):
    """
    Receive Investor Flow Payment
    ---
    tags:
      - Investor Flow
    summary: >
      Save the payment and post a submitted Journal Entry: Dr Company Bank Account / Cr Investor Deposit
      Account (both from Custom Investor Settings; the investor is the party). paid_from (the investor's
      Bank Account) is saved as a reference. Creates the earning schedule, sets Contract Status to Paid
      and Status to Received.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - payment_date
              - ref_no
              - payment_mode
              - amount_paid
              - paid_from
            properties:
              payment_date:
                type: string
                format: date
              ref_no:
                type: string
              payment_mode:
                type: string
                enum: [Wire Transfer, Cheque, Cash, Bank Draft]
              amount_paid:
                type: integer
              paid_from:
                type: string
                description: Bank Account ID of the investor (from get_investor_bank_accounts).
    responses:
      200:
        description: Payment received successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = service.receive_payment(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Payment received successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Receive Investor Flow Payment Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_schedules():
    """
    Get Investor Flow Schedule
    ---
    tags:
      - Investor Flow
    summary: Calculate the payout schedule for the given terms. Nothing is saved.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investment_amount
              - repayment_frequency
              - maturity_date
              - interest_rate
              - first_repayment_date
            properties:
              investment_amount:
                type: integer
              repayment_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              maturity_date:
                type: string
                format: date
              interest_rate:
                type: number
              first_repayment_date:
                type: string
                format: date
              penalty_rate:
                type: number
    responses:
      200:
        description: Schedule calculated successfully.
    """
    try:
        data = parse_api_payload()
        result = service.get_schedule(data)

        return send_response(
            status="success",
            message="Schedule calculated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Flow Schedule Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_earnings(page=1, page_size=20):
    """
    List Investor Earnings
    ---
    tags:
      - Investor Flow
    summary: Paginated list of Received Investor Flows with the main Earning & Settlement fields.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID, investor (Customer ID) or customer name.
      - in: query
        name: investment_product
        schema:
          type: string
        description: A single value or a JSON array of values.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        records, total_records, total_pages = service.get_investor_earnings(args, page, page_size)

        response_data = {
            "success": True,
            "message": "Investor Earnings retrieved successfully.",
            "data": records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success",
            message="Success",
            data=response_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Earnings Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_earning_by_id(id=None):
    """
    Get Investor Earning By ID
    ---
    tags:
      - Investor Flow
    summary: Earning & Settlement details and the full schedule of a Received Investor Flow.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        data = service.get_investor_earning_by_id(investor_flow_id)

        return send_response(
            status="success",
            message="Investor Earning retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Earning By ID Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_earning(id=None):
    """
    Update Investor Earning
    ---
    tags:
      - Investor Flow
    summary: Edit the Earning & Settlement details and existing schedule rows. Rows cannot be added or removed.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              amount_invested:
                type: integer
              frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              mat_date:
                type: string
                format: date
              rate_of_interest:
                type: number
              first_repay_date:
                type: string
                format: date
              rate_of_penalty:
                type: number
              schedule:
                type: array
                items:
                  type: object
                  required:
                    - name
                  properties:
                    name:
                      type: string
                      description: Schedule row ID.
                    payment_date:
                      type: string
                      format: date
                    principal_amount:
                      type: number
                    interest_amount:
                      type: number
                    penalty_amount:
                      type: number
                    total_payment:
                      type: number
    responses:
      200:
        description: Investor Earning updated successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = service.update_investor_earning(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Earning updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Earning Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_accounting_settings():
    """
    Get Investor Accounting Settings
    ---
    tags:
      - Investor Flow
    summary: Company Bank Account (Paid To) and Investor Deposit Account from Custom Investor Settings.
    responses:
      200:
        description: Settings retrieved successfully.
    """
    try:
        data = service.get_investor_accounting_settings()

        return send_response(
            status="success",
            message="Investor accounting settings retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Accounting Settings Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def pay_investor_earning_row(id=None):
    """
    Pay Investor Earning Row
    ---
    tags:
      - Investor Flow
    summary: >
      Pay one schedule row. Accrues it first if the daily job has not (Dr Interest / Penalty Expense,
      Cr Interest Payable), then posts Dr Investor Deposits (principal) + Dr Interest Payable (accrued)
      + Dr Penalty Expense (penalty added after accrual) / Cr Company Bank (total). The row becomes Paid.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - row
            properties:
              row:
                type: string
                description: Schedule row ID.
              payment_date:
                type: string
                format: date
                description: Posting date of the payout (default today).
              ref_no:
                type: string
    responses:
      200:
        description: Schedule row paid successfully.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = service.pay_investor_earning_row(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Schedule row paid successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Pay Investor Earning Row Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def close_investor_flow(id=None):
    """
    Close Investor Flow
    ---
    tags:
      - Investor Flow
    summary: Maturity - when every schedule row is Paid, set Status to Matured.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
    responses:
      200:
        description: Investor Flow closed successfully.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = service.close_investor_flow(investor_flow_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow closed successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Close Investor Flow Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_settings():
    """
    Get Investor Settings
    ---
    tags:
      - Investor Flow
    summary: >
      Custom Investor Settings (the five GL accounts) and, per field, the accounts it accepts
      in the user's default company.
    responses:
      200:
        description: Investor settings retrieved successfully.
    """
    try:
        data = accounting.get_settings_for_setup()

        return send_response(
            status="success",
            message="Investor settings retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Settings Error")


@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_investor_settings():
    """
    Update Investor Settings
    ---
    tags:
      - Investor Flow
    summary: Save the five GL accounts of Custom Investor Settings (all required, one company).
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - company_bank_account
              - investor_deposit_account
              - interest_payable_account
              - interest_expense_account
              - penalty_expense_account
            properties:
              company_bank_account:
                type: string
                description: Asset account, Account Type Bank or Cash.
              investor_deposit_account:
                type: string
                description: Liability account, blank Account Type.
              interest_payable_account:
                type: string
                description: Liability account, blank Account Type.
              interest_expense_account:
                type: string
                description: Expense account.
              penalty_expense_account:
                type: string
                description: Expense account.
    responses:
      200:
        description: Investor settings saved successfully.
    """
    try:
        data = parse_api_payload()
        result = accounting.update_settings(data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor settings saved successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Investor Settings Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_maturities(page=1, page_size=20):
    """
    List Investor Maturities
    ---
    tags:
      - Investor Flow
    summary: Investments by maturity state, with what is still owed on each.
    parameters:
      - in: query
        name: view
        schema:
          type: string
          enum: [due, upcoming, closed]
        description: due = Received and maturity date reached (default); upcoming = Received, not yet due;
          closed = Matured / Renewed.
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID, investor (Customer ID) or customer name.
      - in: query
        name: investment_product
        schema:
          type: string
        description: A single value or a JSON array of values.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        records, total_records, total_pages = maturity.get_investor_maturities(args, page, page_size)

        response_data = {
            "success": True,
            "message": "Investor Maturities retrieved successfully.",
            "data": records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_records,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

        return send_response_list(
            status="success",
            message="Success",
            data=response_data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Maturities Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_maturity_by_id(id=None):
    """
    Get Investor Maturity By ID
    ---
    tags:
      - Investor Flow
    summary: >
      Maturity summary: what is still owed, whether it is due, the amount Renew would carry over
      and the pre-filled terms for the renewed investment.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        data = maturity.get_investor_maturity_by_id(investor_flow_id)

        return send_response(
            status="success",
            message="Investor Maturity retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Maturity By ID Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def redeem_investor_flow(id=None):
    """
    Redeem Investor Flow
    ---
    tags:
      - Investor Flow
    summary: >
      On or after the maturity date: pay every unpaid schedule row (principal + interest) from the
      Company Bank, dated today, and set Status to Matured.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = maturity.redeem_investor_flow(investor_flow_id)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow redeemed successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Redeem Investor Flow Error")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def renew_investor_flow(id=None):
    """
    Renew Investor Flow
    ---
    tags:
      - Investor Flow
    summary: >
      On or after the maturity date: pay the interest still owed in cash and carry the unpaid principal
      (whole rupees) into a new Draft investment for the same investor. Old Status becomes Renewed.
    parameters:
      - in: query
        name: id
        schema:
          type: string
        required: true
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investment_product
              - interest_rate
              - repayment_frequency
              - first_repayment_date
              - maturity_date
            properties:
              investment_product:
                type: string
              interest_rate:
                type: number
              repayment_frequency:
                type: string
                enum: [Monthly, Weekly, Bi-Weekly, Quarterly, Yearly]
              first_repayment_date:
                type: string
                format: date
              maturity_date:
                type: string
                format: date
              penalty_rate:
                type: number
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")

        result = maturity.renew_investor_flow(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Investor Flow renewed successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Renew Investor Flow Error")
