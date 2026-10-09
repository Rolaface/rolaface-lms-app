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
    summary: Delete an Investor Flow (only Draft or Cancelled; not a renewed investment).
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
def add_fund_record(id=None):
    """
    Add Fund Record
    ---
    tags:
      - Investor Flow
    summary: >
      Save a fund received from the investor as a Draft record (Approved investments). No Journal Entry
      is posted until the record is approved. Paid to / Paid from GLs come from Custom Investor Settings.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
        description: Investor Flow ID.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - paid_date
              - mode_of_payment
              - reference_number
              - amount
            properties:
              paid_date:
                type: string
                format: date
              mode_of_payment:
                type: string
                enum: [Wire Transfer, Cheque, Cash, Bank Draft]
              reference_number:
                type: string
              amount:
                type: number
                description: At most the investment amount minus the approved and draft records.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")
        result = service.add_fund_record(investor_flow_id, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Fund record saved as Draft.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Add Fund Record Error")

@frappe.whitelist(allow_guest=True, methods=["PUT", "PATCH"])
def update_fund_record(id=None, record=None):
    """
    Update Fund Record
    ---
    tags:
      - Investor Flow
    summary: >
      Edit a Draft fund record.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
        description: Investor Flow ID.
      - in: query
        name: record
        required: true
        schema:
          type: string
        description: Fund record (row) ID.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - paid_date
              - mode_of_payment
              - reference_number
              - amount
            properties:
              paid_date:
                type: string
                format: date
              mode_of_payment:
                type: string
                enum: [Wire Transfer, Cheque, Cash, Bank Draft]
              reference_number:
                type: string
              amount:
                type: number
                description: At most the investment amount minus the approved and draft records.
    """
    try:
        data = parse_api_payload()
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")
        record_name = record or frappe.request.args.get("record")
        if not record_name:
            raise frappe.ValidationError("Fund record ID is required.")
        result = service.update_fund_record(investor_flow_id, record_name, data)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Fund record updated successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Update Fund Record Error")

@frappe.whitelist(allow_guest=True, methods=["DELETE"])
def delete_fund_record(id=None, record=None):
    """
    Delete Fund Record
    ---
    tags:
      - Investor Flow
    summary: >
      Delete a Draft fund record.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
        description: Investor Flow ID.
      - in: query
        name: record
        required: true
        schema:
          type: string
        description: Fund record (row) ID.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")
        record_name = record or frappe.request.args.get("record")
        if not record_name:
            raise frappe.ValidationError("Fund record ID is required.")
        result = service.delete_fund_record(investor_flow_id, record_name)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Fund record deleted successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Delete Fund Record Error")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def approve_fund_record(id=None, record=None):
    """
    Approve Fund Record
    ---
    tags:
      - Investor Flow
    summary: >
      Post the record's Journal Entry (Dr Paid to GL / Cr Paid from GL, party = investor) and count it
      in Fund Received. Fund Status becomes Partial, or Paid (Status Paid) once the full amount is approved.
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
        description: Investor Flow ID.
      - in: query
        name: record
        required: true
        schema:
          type: string
        description: Fund record (row) ID.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")
        record_name = record or frappe.request.args.get("record")
        if not record_name:
            raise frappe.ValidationError("Fund record ID is required.")
        result = service.approve_fund_record(investor_flow_id, record_name)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Fund record approved successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Approve Fund Record Error")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def cancel_fund_record(id=None, record=None):
    """
    Cancel Fund Record
    ---
    tags:
      - Investor Flow
    summary: >
      Cancel a Draft record, or an Approved one together with its Journal Entry (the amount no longer
      counts in Fund Received).
    parameters:
      - in: query
        name: id
        required: true
        schema:
          type: string
        description: Investor Flow ID.
      - in: query
        name: record
        required: true
        schema:
          type: string
        description: Fund record (row) ID.
    """
    try:
        investor_flow_id = id or frappe.request.args.get("id")
        if not investor_flow_id:
            raise frappe.ValidationError("Investor Flow ID is required.")
        record_name = record or frappe.request.args.get("record")
        if not record_name:
            raise frappe.ValidationError("Fund record ID is required.")
        result = service.cancel_fund_record(investor_flow_id, record_name)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Fund record cancelled successfully.",
            data=result,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        frappe.db.rollback()
        return handle_api_error(e, "Cancel Fund Record Error")

@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_fund_records(page=1, page_size=20):
    """
    List Fund Records
    ---
    tags:
      - Investor Flow
    summary: Every fund record (one row per receipt) with its investment, investor and Record Status.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches investment ID, investor (Customer ID) or investor name.
      - in: query
        name: record_status
        schema:
          type: string
        description: Draft / Approved / Cancelled - a single value or a JSON array of values.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        records, total_records, total_pages = service.get_fund_records(args, page, page_size)

        response_data = {
            "success": True,
            "message": "Fund records retrieved successfully.",
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
        return handle_api_error(e, "Get Fund Records Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_funds(page=1, page_size=20):
    """
    List Investor Funds
    ---
    tags:
      - Investor Flow
    summary: Investments from approval onward with fund received, remaining fund and Fund Status.
    parameters:
      - in: query
        name: search
        schema:
          type: string
        description: Matches ID, investor (Customer ID) or investor name.
      - in: query
        name: fund_status
        schema:
          type: string
        description: Pending / Partial / Paid - a single value or a JSON array of values.
      - in: query
        name: status
        schema:
          type: string
        description: Approved / Paid - a single value or a JSON array of values.
    """
    try:
        args = frappe.local.form_dict
        page, page_size = int(page), int(page_size)

        records, total_records, total_pages = service.get_investor_funds(args, page, page_size)

        response_data = {
            "success": True,
            "message": "Investor Funds retrieved successfully.",
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
        return handle_api_error(e, "Get Investor Funds Error")


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
    summary: >
      Edit existing schedule rows. The Earning & Settlement details are read-only (a changed value is
      refused). Rows cannot be added or removed.
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
def get_record_fund_accounts():
    """
    Get Record Fund Accounts
    ---
    tags:
      - Investor Flow
    summary: >
      From Custom Investor Settings: the Credit GL (Investor Creditor GL) and, per Mode of Payment,
      the Debit GL the money lands in (null when not set).
    responses:
      200:
        description: Accounts retrieved successfully.
    """
    try:
        data = service.get_record_fund_accounts()

        return send_response(
            status="success",
            message="Record Fund accounts retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Record Fund Accounts Error")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_investor_fund_by_id(id=None):
    """
    Get Investor Fund By ID
    ---
    tags:
      - Investor Flow
    summary: An investment's fund received, remaining fund, Fund Status and every recorded fund row.
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

        data = service.get_investor_fund_by_id(investor_flow_id)

        return send_response(
            status="success",
            message="Investor Fund retrieved successfully.",
            data=data,
            status_code=200,
            http_status=200,
        )
    except Exception as e:
        return handle_api_error(e, "Get Investor Fund By ID Error")


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
    summary: >
      Save the GL accounts of Custom Investor Settings (one company). Investor Creditor GL is required;
      the others are checked when set.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - investor_creditor_account
            properties:
              investor_creditor_account:
                type: string
                description: Liability account, blank Account Type (common for all investors; party = investor).
              investor_cash_account:
                type: string
                description: Cash GL - Asset, Account Type Bank or Cash.
              cheque_account:
                type: string
                description: Asset, Account Type Bank or Cash.
              bank_draft_account:
                type: string
                description: Asset, Account Type Bank or Cash.
              wire_transfer_account:
                type: string
                description: Asset, Account Type Bank or Cash.
              company_bank_account:
                type: string
                description: Asset, Account Type Bank or Cash (payouts).
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
