# LOS (Loan Origination System) — Build Spec

Living spec of the LOS backend being built in this Frappe app. Read this first in any new chat.
Last updated: 2026-10-06.

## 1. Context

| Item | Value |
|---|---|
| Backend | Frappe **v16** app `rolaface_lms_app`, at `/Users/akku/data/code/frappe/frappe-bench/apps/rolaface_lms_app` |
| Python | 3.14 (Frappe requires it) |
| Dev site | `lms.local` (bench at `/Users/akku/data/code/frappe/frappe-bench`, `bench start` serves port 8000) |
| Frontend | React app at `/Users/akku/data/code/rolaface/rolaface-lms` (branch `feat-los-loan-application`, dev server on port 5174; its uncommitted `vite.config.ts` proxies `/api` to `http://lms.local:8000` and belongs to the owner). The setup screens (section 5.7), the Loan Application and the four stage workspaces (sections 7.3–7.5) are wired to the real APIs; the rest is still a **prototype with dummy data**: use it as a reference for what exists, not as a requirement list |
| Git (backend) | Branch `version-16`, latest `6b63226` (merge of feat/search-api-lms). Uncommitted (2026-10-07): loan application constant / utils / service / api, `modules/workflow/service.py` fix, the Loan Application DocType JSON + controller (`custom_status`, `monthly_income`), and this spec |
| Git (frontend) | Branch `feat-los-loan-application` on top of `a118fb7` (main). Uncommitted (2026-10-07): the Loan Application modal and list, `LoanApplicationApi.ts`, `stageData.tsx`, the four stage modals, `stages.ts` / `useApplicationWorkflow.tsx`, routes, `.claude/launch.json` |
| Other apps on the site | erpnext, lending (`Loan`, `Loan Product`, `Loan Security Type`), hrms |
| Swagger | `GET /api/method/rolaface_lms_app.modules.los.docs.api.get_openapi_spec`, generated from docstrings |

## 2. Working rules (agreed with the owner)

- **Keep it simple. Do not over-engineer.** No endpoints, fields or tables "just in case". Ask before adding anything not requested.
- **One HTTP method per endpoint**: POST = create, PUT = update / status change / page save, DELETE = delete, GET = read. (Two methods on one endpoint shows as duplicate Swagger entries.)
- **No test code in the repo** for now. Test from the outside (see section 9).
- **No unnecessary comments**; the module code has essentially none.
- When asked for a DocType spec, give **field tables** (label, fieldname, type, options, mandatory), not code.
- **Authorization / role checks are deferred** by the owner. Do not add them unless asked.
- Never commit unless asked. The owner's `.gitignore` change is theirs; leave it out of commits.
- Don't wipe or modify the owner's data during tests (see section 9).
- One pre-screening rule set and one eligibility rule **per loan product**.

## 3. Code structure (follow exactly)

Each module lives in `rolaface_lms_app/modules/los/<module>/` and mirrors the owner's `document_setup` module:

| File | Contents |
|---|---|
| `constant.py` | `*_DOCTYPE` names, `ALLOWED_UPDATE_FIELDS`, `ALLOWED_SORT_FIELDS`, `DEFAULT_SORT_BY` / `DEFAULT_SORT_ORDER`, `SEARCH_FIELDS`, `RETURN_FIELDS_GET_ALL` (and `RETURN_FIELDS_GET_BY_ID`) |
| `utils.py` | `validate_*` functions (return cleaned values), `parse_*_row`, `build_*_filters`, and private helpers |
| `service.py` | `_ensure_exists`, then create, update, `get_<x>_by_id`, `get_<x>s` (list), delete |
| `api.py` | `@frappe.whitelist(methods=[...])` functions, in the same order, with no section-divider comments. Each is `try: ... frappe.db.commit(); return send_response(...)` and `except Exception as e: return handle_api_error(e, "...")` |

Other conventions:
- Keep `typing.Dict` / `List` like the existing modules.
- Writes use `ignore_permissions=True`.
- Request data comes from `common.request_args()` (query, form and JSON body merged). Not `frappe.form_dict`, because the Bearer auth hook empties it.
- Errors come from `utils/api_response.handle_api_error`:

  | Exception | HTTP status |
  |---|---|
  | `DoesNotExistError` | 404 |
  | `DuplicateEntryError` / `LinkExistsError` / `TimestampMismatchError` | 409 |
  | `PermissionError` | 403 |
  | `ValidationError` | 400 (real message) |
  | Anything else | 500 with a generic message; the detail goes to the Error Log (also kept for GET requests) |

- Responses:
  - `send_response` puts the result under `message.data`.
  - `send_response_list` puts `data` and `pagination` at the top level.
- Swagger docstring format: a title line, `---`, then OpenAPI YAML (tags, summary, parameters, requestBody with `example` or named `examples`, responses).
- Shared helpers:
  - `modules/los/common.py`: pagination, order_by, search, `add_date_range` (a lone `to_date` covers the whole day), `json_contains` (escaped LIKE on JSON lists), `name_map`, `load_json` / `dump_json`, `check_version` / `table_version`.
  - `modules/los/versioned.py`: the version lifecycle (section 6).

## 4. Pipeline (big picture)

```
Setup:  Loan Type Tree · Channels · Product Assignment · Document Setup · Pre-screening rules · Eligibility rules
Flow:   Loan Application → Pre-screening → Appraisal → Underwriting → Offer & Signing → Loan booked (lending `Loan`)
```

## 5. Setup modules (built)

### 5.1 Loan Type Tree: `Custom LOS Loan Type Tree`
- **Levels:**
  - 1 = Loan Type, 2 = Sub-type, 3 = Purpose.
  - Fields: `applicant_type` (Individual / Business), `node_name`, `level`, parent `parent_custom_los_loan_type_tree`, `loan_type`, `sub_type`, `is_active`.
- **DocType settings:**
  - IDs are hashes, and `allow_rename = 0`.
  - `is_tree = 1` but the controller is a plain Document (lft/rgt are not used).
- **APIs:**
  - Node CRUD: `create_node`, `update_node`, `get_node_by_id`, `delete_node`, `enable_node`, `disable_node`. Disabling a node cascades to its descendants.
  - Lookups for the application's first page: `get_loan_types`, `get_sub_types`, `get_purposes`.
  - Whole-tree screen: `get_loan_type_setup` and `save_loan_type_setup`.
    - The payload is `{Individual: [{id, name, subTypes: [{id, name, purposes: [...]}]}], Business: [...]}`.
    - Items without an id are created. Stored items left out are deleted, or deactivated if they are in use.
    - The optional `version` gives a 409 on concurrent edits.
    - **The UI must load with `include_inactive=1`**; otherwise saving deletes disabled items.

### 5.2 Channels: `Custom LOS Channel`
- Named by `channel_name`.
- APIs: `create_channel`, `update_channel` (a real rename), `get_channel_by_id`, `get_channels`, `delete_channel` (refused while rules use it), `enable_channel`, `disable_channel`.
- The controller's `after_rename` hook rewrites the channel in product rule `sources` JSON, so API and Desk renames both stay consistent.
- Channels today: `Branch` and `USSD`. Whether users should be able to add channels from the UI is an open question.

### 5.3 Product Assignment: `Custom LOS Product Assignment Rule` and `Custom LOS Product Assignment Settings` (single)
- **One rule per loan product, with no priority.**
  - The rule's ID **is the loan product code** (named by `product`, which is unique).
  - Renaming is disabled.
- **Rule fields:**
  - `product`, `product_name` (filled from the Loan Product), `is_active`.
  - `sources` (JSON list of channel IDs), `loan_types` (JSON list of level-1 node IDs).
  - `condition` (JSON `{join: AND|OR, groups: [{name, join, clauses: [{variable, operator, value}]}]}`).
  - Operators are `= <> > >= < <=`, plus `between` for numbers (`value` and `value2`, both ends included, `value2` ≥ `value`).
  - **Variables (2026-10-08) are the loan application's own fields**, defined in `engine/product_assignment.py` (`VARIABLES`) and served by `get_condition_variables` (with live options): customer type, loan sub-type, loan purpose, requested amount, tenure, repayment frequency, credit score, age, gender, marital status, citizenship (Zambian / Foreign national), employment status / type, work experience, monthly income / obligations, debt-to-income %, business type, years in business, number of directors, collateral type (matches if any collateral row has it) and total collateral value. Select options come from the DocType, the loan type tree and Loan Security Types. A missing fact never matches. The old variables (`loan_amount`, `tenor`, `net_monthly_income`, `vehicle_condition`, …) are gone; the frontend builder loads the list from the API instead of its own copy.
- **Settings:** `several_match` (First match / Manual Review; shown in the UI for the future, not used: the owner's rule is that rules must not overlap, so a double match is a Conflict), `no_match` (Manual Review / Default Product), `default_product` (JSON `{loan_type_id: product}`).
- **APIs (11):**
  - `create_rule` (409 if the product already has a rule).
  - `update_rule` (only sources, loan types and condition; the product can't change).
  - `get_rule_by_id`.
  - `get_rules` (paginated). Filters: `product`, `source`, `loan_type`, `is_active`, `has_condition`, `ids`, dates. Search covers product ID and name. Sort: `product_name` (default), name, is_active, creation, modified.
  - `delete_rule`, `enable_rule`, `disable_rule`.
  - `get_settings` / `update_settings`.
  - `test_rules` (POST: source, loan_type or purpose, facts). Status is Rule matched / Loan type default / Manual review / **Conflict**. It skips inactive rules and disabled products.
  - `get_condition_variables`.
- **More than one match means the rules were set up wrongly:** `test_rules` reports it as Conflict so the admin can fix them. Detecting overlapping rules automatically when they're saved is future scope.
- **Removed:** `get_product_assignment`, `save_product_assignment` (the whole-table save that existed for priority) and `resolve_product` (now `test_rules`). The frontend now uses `get_rules`, and its Matching panel loads `get_settings` and saves the whole form with `update_settings`.

### 5.3a Product assignment engine (`modules/los/engine/`, 2026-10-08)
- `engine/product_assignment.py` owns the variables, `application_facts(application)` (builds the facts from an application in the API shape: derived age, years in business, citizenship, income / obligation totals, DTI, collateral types and value, sub-type / purpose names), `match_product(source, loan_type, facts)` and `assign_product(application)`. `test_rules` and the loan application both use it, so there is one matcher.
- `assign_product` returns the match (Rule matched / Loan type default / Manual review / Conflict, `product`, `product_name`, `reason`) plus the product's `rate_of_interest`, `maximum_loan_amount` and its Document Setup `documents` (null when it has none).
- **API:** `engine.api.assign_loan_product` (POST, the application as entered so far; nothing is saved).
- **When it runs:**
  - Loan application form: leaving the Collateral step (Next), jumping ahead to Documents / Simulation by tab, opening a Draft for edit (silently), and again on Save. No product (no match without a default, or a Conflict) blocks moving on with a message. If the product changed by Save, the form goes back to Documents with a notice.
  - Server: `create_loan_application` and Draft updates with application details assign `loan_product` themselves (authoritative). After the application leaves Draft the product is fixed.
  - Workflow: not checked. The owner chose not to block submitting a Draft without a `loan_product` in the controller (2026-10-12). The form can't save without one; LA-2026-00001 / 00002 and Drafts created through the API can still have none.
- **Documents step:** the tiles are that product's Document Setup list (name, required, description), all from the backend; nothing is hardcoded in the frontend. Same layout, one generic icon and the standard file guidelines. Without a setup the step says no documents are set up. Business director NRC / photo uploads are unchanged. On save only the product's documents (plus director documents) are sent. Read-only views show the uploaded documents.
- **Simulation and summary:** the product's interest rate replaces the 25% placeholder; its maximum loan amount caps the amount slider and is checked before save. The summary shows "Product: …".
- **Data (2026-10-10, owner's request):** 17 enabled products, one rule each, split by sub-type / purpose so no two rules overlap (checked against all applications and 18 sample cases). Each product has a Document Setup of 2–3 documents with descriptions (PL-001's is the owner's, 4 documents, no descriptions).

  | Loan type | Product (rate, max) | Rule |
  |---|---|---|
  | Personal | PL-EDU Education Loan (26%, 150k) | Education; score ≥ 600; ≤ 150k (Branch, USSD) |
  | Personal | PL-MED Medical Loan (27%, 100k) | Medical; score ≥ 550; ≤ 100k (Branch, USSD) |
  | Personal | PL-PAY Public Service Payroll Loan (28%, 400k) | other purposes; Salaried + Government, age 18–58; DTI ≤ 50%; ≤ 400k (Branch, USSD) |
  | Personal | PL-002 Standard Personal Loan2 (12.5%, 500k) | other purposes; score ≥ 750, Salaried, not Government; ≤ 500k |
  | Personal | PL-001 Standard Personal Loan (17%) | other purposes; score 600–749, not Government; DTI ≤ 45% |
  | Vehicle | VF-NEW New Vehicle Finance (24%, 1.5M) | New Car / New Bike; score ≥ 620; ≤ 60 months |
  | Vehicle | VF-USED Pre-owned Vehicle Finance (27%, 650k) | Used Car / Used Bike; score ≥ 650; ≤ 48 months |
  | Home | HL-MORT Home Purchase Mortgage (23.5%, 3.5M) | Home Purchase; age 21–55, Zambian; score ≥ 650 |
  | Home | HOME HOME LOAN (17%) | Home Construction; age 21–60, Zambian; score ≥ 650 |
  | Home | HL-PLOT Residential Plot Loan (25%, 600k) | Land Purchase; Zambian; score ≥ 620; ≤ 60 months |
  | Asset Finance | AF-CV Commercial Vehicle Finance (25%, 3.5M) | Commercial Vehicles; ≥ 2 years in business |
  | Asset Finance | AF-EQP Equipment & Machinery Finance (24%, 5M) | Equipment; ≥ 2 years in business |
  | Agribusiness | AG-CROP Seasonal Crop Input Loan (22%, 750k) | Crop Finance; ≤ 12 months |
  | Agribusiness | AG-LIVE Livestock Finance (23%, 1M) | Livestock Finance; score ≥ 600; ≤ 36 months |
  | Working Capital | WC-INV Invoice Discounting Facility (28%, 2.5M) | Invoice Discounting; ≥ 2 years; ≤ 6 months |
  | Working Capital | WC-LPO LPO Financing (30%, 2M) | LPO Financing; ≥ 1 year; ≤ 6 months |
  | Working Capital | DFSL Diversity Financial Solutions (10%) | Overdraft; ≥ 2 years |

  Branch only unless noted. Defaults when no rule matches: Personal → PL-001, Vehicle → VF-USED, Home → HOME, Working Capital → DFSL, Agribusiness → AG-CROP, Asset Finance → AF-EQP. Applications past Draft keep the product they were given on 2026-10-08; Drafts pick up the current rules when saved. New charge items: Credit Life Insurance, Valuation Fee, Legal Fee, Tracking Device Fee. New loan categories: CONS, VEH, ASSET, AGRI, SME.

### 5.3b Pre-screening and eligibility engines (`modules/los/engine/`, 2026-10-12)
- **Trigger (owner's decision):** the workflow action **Submit for Pre-Screening**. `modules/workflow/constant.ACTION_HANDLERS` maps (doctype, action) to a handler; `apply_dynamic_workflow_action` calls it after the transition and returns its result as `action_result`. The LOS handler is `engine.pipeline.on_submit_for_prescreening`. The result never blocks the move; if the engine raises, the move still happens and Manual Review is stored with the error (savepoint + Error Log).
- **Files:** `facts.py` (`application_facts`, shared by all three engines; `field_options`), `prescreening.py` (`FIELDS`, `prescreening_fields()`, pure `run_prescreening(groups, facts)`), `eligibility.py` (pure `run_eligibility(rule, facts, product)`), `pipeline.py` (loads the Active version effective today, builds facts once, runs pre-screening then eligibility; `evaluate_application`, `on_submit_for_prescreening`, test helpers).
- **Order:** pre-screening first; eligibility runs unless pre-screening is Not Eligible (it also runs on Manual Review). Overall `verdict` = worst of both (Not Eligible > Manual Review > Eligible with Warnings > Eligible). No product, or no Active rule set / rule effective today → Manual Review with the reason.
- **Stored (save):** `prescreening_data.engine` = the full result plus `trigger` (Submit for Pre-Screening / Officer), `ran_on`, `ran_by`, `overrides`, rule set and rule names and versions; `eligible_amount`; `custom_status` = verdict only on the workflow trigger. Saving is only allowed while the application is in Pre-Screening.
- **APIs (POST, `engine/api.py`):** `evaluate_application` {application, overrides, save} (the flow; the Pre-screening screen previews with save 0 and saves on Submit), `run_prescreening` and `run_eligibility` (testing: {application} or {data, loan_product}). The setup screen's `test_ruleset` uses the same `run_prescreening`.
- **Overrides** (the officer's figures): `credit_score` (300–850), `requested_amount` (> 0), `income` / `obligations` (lists of {source, monthly_amount}, replacing the application's lines).
- **Pre-screening fields** are the application's own (22): age, gender, marital status, nationality (Zambian / Non-Zambian), customer type, employment status / type, employer, work experience (years), monthly income / obligations, debt-to-income, credit score, loan amount / tenure / sub-type / purpose / repayment frequency, business type, years in business, collateral type / value. Options come from the DocType, the tree and Loan Security Types. Dropped (no data yet): location, previous defaults, active loans, overdue amount, risk category, customer since, date of birth. **A rule whose value is missing fails at its own severity.**
- **Eligibility formula** (the owner's Review & Publish screen):
  - Recognised income = Σ line × its source's recognition % (included sources; excluded → 0; a source the rule doesn't list → `other_income_recognition` %). Names match exactly or by prefix ("Rental" → "Rental Income").
  - Obligations = Σ line × its source's % (unlisted → 100%).
  - Limits: income = recognised × `salary_multiple`; affordability = max(0, recognised × `max_emi_ratio`% − obligations) × tenure × `affordability_buffer`%; credit = band multiple × basis income (Net Salary, also for "Basic Salary" bands; recognised income for "Total Income" bands); collateral (only if the rule lists collateral types) = Σ value × (1 − haircut%) × max LTV%; product = `product_max` (else the Loan Product maximum). Eligible = the lowest; `limiting_factor` names it.
  - Not Eligible (amount 0): no recognised income, no band or band decision Decline, a hard stop hit, debt service ratio (obligations ÷ recognised income) above `max_dti_ratio`, or an eligible amount of 0.
  - Manual Review: band decision Conditional / Manual Review, a manual-review rule hit, or no income entered yet (business applications have no income lines until the officer enters them).
  - Hard stops and manual reviews checked: Credit Score, Debt Service Ratio (DSR) / DSR Ratio, EMI-to-Income Ratio ((obligations + new instalment at the product rate) ÷ recognised income), Loan Amount. Others (NPA, fraud, blacklist, DPD, insolvency, KYC, misrepresentation) are returned in `not_checked`. Internal bands, the risk tier and pre-approval tiers are not used.
- **Frontend (Pre-screening screen, design kept):** the frontend formula and placeholder policy are gone (`calcEligibility` removed). The screen previews `evaluate_application` 400 ms after an edit (score, income, liabilities, amount); the DTI bar, maximum eligible, limit assessment (now the engine's five limits, product code and rule version) and the footer text come from the result. Submit is allowed on Eligible / with Warnings within the eligible amount and on Manual Review; blocked on Not Eligible. Submit saves the stage data, then calls `evaluate_application` with save. `prescreening_data.policy.max_dti` (read by Appraisal) and `result` / `dti` (read by Offer) keep their keys.
- **Data (2026-10-12):** every product has an Active pre-screening rule set (PSR-00010–00012 converted: Permanent / Contract → Salaried, employment months → experience years, rules on dropped fields removed; PSR-00014–00027 new) and an Active eligibility rule (ELR-00005–00017 new; the owner's HOME draft ELR-00002 "New Test Rule" was filled and activated as "Home Construction Loan Eligibility"). The owner's PL-001 and DFSL eligibility rules list collateral types, so an application without that collateral gets a collateral limit of 0 → Not Eligible. PL-001's rule also lists Property and Fixed Deposit, which are not Loan Security Types, so applications can only ever carry its Vehicle type. The owner's PL-001 rule set warns at debt-to-income ≤ 40% while its eligibility rule allows a maximum EMI ratio of 30%, so a warning-level applicant always ends Not Eligible.
- **Testing (2026-10-12):** per-product suite through the real pipeline and workflow, rolled back: 600 checks (every rule broken alone, ANY groups, missing values, every credit band, DSR breach, manual-review amounts, no income, unlisted / prefixed income sources, collateral, requested > eligible) and 222 failure-path checks (Blocking → eligibility skipped and Not Eligible; Review / Warning → eligibility still runs, overall = worst; eligibility decline after a pass; stale eligible amount replaced). Fixed from it: a Not Eligible result kept the previous `eligible_amount` (now 0, and every save overwrites it); the seeded rule sets' debt-to-income Warning limits were above their products' max EMI ratio (lowered to max EMI − 10 as v1.1 of PL-PAY, PL-EDU, PL-MED, VF-NEW, VF-USED, HL-MORT, HL-PLOT).
- **Browser test (2026-10-13)** on seeded `LA-2026-00047` (PL-002) and `LA-2026-00004` (HOME, no credit score), both restored exactly afterwards: Submit for Pre-Screening from the ⋮ menu (Eligible, K101,790; and Not Eligible with eligibility skipped, amount 0), stage list status, live preview on income edits (Eligible / over the limit / Not Eligible on DSR / Manual Review on EMI-to-income), Submit on Manual Review (stage data + `evaluate_application` save, officer overrides stored), read-only view from the stored result, limit assessment tab, setup builder and Test tab with the new fields. Fixed from it: footer reason had a double full stop and "Manual review — Manual review:"; the reason was hidden while data was incomplete; DTI showed "Policy cap 100%" when eligibility was skipped (skipped results now carry the rule's `max_dti_ratio`, `max_emi_ratio` and the product rate); the manual income box was editable in read-only view. Old applications without a credit score can't be completed on the screen (the prototype has no manual credit entry).
- **Test data reset (2026-10-14, owner's request):** the loan application table was emptied (all 92 rows including the owner's LA-2026-00001 / 00002, their child rows, 136 addresses, versions, comments, todos) after a backup to `sites/lms.local/private/backups/los_applications_before_truncate_2026-10-14.sql`, and the `LA-2026-` series reset. 96 Draft applications were then generated (LA-2026-00001 – 00096) through `create_loan_application`, one applicant per scenario, covering every product: Pass, Pass with the request above the eligible amount, Warning (products with a debt-to-income warning rule), Review (credit below the review threshold, or HOME's debt-to-income review rule), Fail on a pre-screening blocking rule, Fail on eligibility (debt-service ratio), and Review for businesses with no income entered. Each case was checked against the assignment and both engines before saving.
- **Not run on existing applications:** applications already in Pre-Screening were moved before the engine existed; the screen previews them live and Submit stores the result.

### 5.4 Document Setup: `Custom LOS Product Document Setup` (the owner's module)
- Named by `loan_product`. `documents` is a JSON list of `[{document_name, is_required, description}]` (description optional, max 280 characters; edited in the setup modal's Description column and shown on the application's upload panel).
- APIs: `create_document_setup`, `update_document_setup`, `get_document_setup_by_id`, `get_document_setups`, `get_products_without_documents`, `delete_document_setup`.

### 5.5 Pre-screening: `Custom LOS Prescreening Ruleset` (`PSR-`)
- **Fields:** `ruleset_name`, `loan_product` (set once), `description`, `version`, `status`, `effective_from` / `effective_to` (editable), `groups` (JSON), `published_by`, `published_on`.
- **`groups` shape:** `[{id, name, logic: ALL|ANY, rules: [{id, field, operator, value, value2, values, date_unit, severity, action, disabled}]}]`.
  - Severities and their default action: Blocking → Reject Application, Warning → Continue with Warning, Review → Send for Manual Review.
  - Operators are word codes: `equals`, `not_equals`, `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`, `between`, `in`, `not_in`, `contains`, `starts_with`, `before`, `after`, `older_than`.
  - The 22 fields are in `constant.FIELDS`, copied from the UI.
- **Verdict order:** Not Eligible > Manual Review > Eligible with Warnings > Eligible.
- **APIs:** `get_rulesets` (one line per product, with `draft_id`), `get_ruleset`, `get_ruleset_versions`, `get_prescreening_fields`, `test_ruleset` (POST facts), `create_ruleset` (groups optional; the first modal only sends name, product and description), `update_ruleset`, `set_ruleset_status`, `delete_ruleset`.
- Publishing validates that the groups are complete and stamps `published_by` / `published_on`.
- **List operators (`in` / `not_in`) take their values in `values`, not `value`.** A frontend bug sent them as `value`, so they were saved as `[]`; fixed on 2026-10-06. Any list rule saved before that needs its values re-entered.
- `older_than` takes `value` (a positive number) and `date_unit` (days / months / years, default months).

### 5.6 Eligibility: `Custom LOS Eligibility Rule` (`ELR-`)
- **Fields:** `rule_name`, `loan_product`, `version`, `status`, effective dates, and 8 JSON sections:

  | Section | Shape |
  |---|---|
  | `income_sources` | list |
  | `obligation_sources` | list |
  | `credit_bands` | list |
  | `internal_bands` | list |
  | `collateral_items` | list of `{type, haircut_pct, max_ltv_pct}` |
  | `formula_params` | object with `other_income_recognition`, `salary_multiple`, `max_emi_ratio`, `max_dti_ratio`, `affordability_buffer`, `product_max` (no `exposure_cap`) |
  | `hard_stops` | list, saved as sent |
  | `manual_reviews` | list, saved as sent |

- Sections may be null for now.
- `collateral_items[].type` should be a **Loan Security Type** name, the same values a loan application's collateral uses.
- `update_eligibility_rule` refuses `loan_product` (fixed after create); status only changes through `set_eligibility_rule_status`.
- **APIs:** `get_eligibility_rules`, `get_eligibility_rule`, `get_eligibility_rule_versions`, `create_eligibility_rule`, `update_eligibility_rule`, `set_eligibility_rule_status`, `delete_eligibility_rule`.

### 5.7 Setup screens in the frontend (state after the 2026-10-06 UI pass)

All live under `src/view/LosConfiguration/`. List rows use the same pattern everywhere: View (eye), Edit (pencil), Delete (bin, drafts only) and a ⋮ menu for status changes, each with a confirmation.

- **Loan Type Setup:** edits are local until **Save setup**, which PUTs the whole tree with ids and `version`. Enable/disable calls the node APIs straight away and cascades to children.
- **Product Assignment:** a rule's loan types come from the tree and its products from enabled Loan Products. The condition builder has `is between`. No priority or drag. Matching panel: default product per active loan type.
- **Eligibility:** a 10-step modal with a single **Save**. A new rule saves as a Draft; saving an Active rule creates the new version and activates it straight away, and refuses if the Review checks fail. Activate / Deactivate is in the list's ⋮ menu. Credit and internal score bands share one component: editable grade, re-sorted on blur, conflict checks. Internal scores are capped at 0–100. The debt-to-income and EMI-to-income sliders run 0–100%. Collateral types are Loan Security Types.
- **Pre-screening:** the list (View / Edit / Delete / ⋮ with Activate, Activate draft, Deactivate, Discard draft) opens a detail screen with Builder, Test, Versions and Audit tabs. View mode is read-only; Edit opens the waiting draft if there is one. The detail screen tracks unsaved changes, asks before leaving, and has an editable Effective From. The Test tab runs the saved version only.

## 6. Version lifecycle (`versioned.py`, shared by pre-screening and eligibility)

- **Statuses:** Draft → Active ⇄ Inactive → Archived. One row per version; `version` is "1.0", "1.1" and so on.
- **Editing:**
  - A **Draft** is edited in place.
  - Editing a live version creates (or reuses) a Draft copy. The response returns that draft; use its name from then on.
  - Archived versions are read-only.
- **Status changes:**
  - `set_*_status` takes `{status: Active | Inactive}`.
  - Activating a Draft archives the previous live version. Its `effective_to` and the new version's `effective_from` default to today only if empty.
  - An Inactive version can be reactivated.
- **Deleting:** only Drafts can be deleted. Versions that have been live are kept (409).
- **Concurrency:** every lifecycle write locks the Loan Product row (`SELECT … FOR UPDATE`) and uses locking reads. Tested: 6 parallel requests produce exactly one rule set, one activation and one draft.
- **Not built:** a scheduler for future-dated activation (possible future scope).

## 7. Loan Application (built: data, CRUD, workflow and stage screens)

### 7.1 DocTypes
- **`Custom LOS Loan Application`**, named `LA-.YYYY.-.#####`, with change tracking on. Tabs:

  | Tab | Contents |
  |---|---|
  | Application | `application_date` (default Today), `company` (required; defaults to the user's company), `channel`, `status`, `stage` (read-only), `workflow_state`, `custom_status` (read-only, indexed), `loan` (read-only). **Customer** section: `customer_type` (New / Existing), `customer` (required if Existing). **Loan Request** section: `applicant_type` (Individual / Business), `loan_type` / `loan_sub_type` / `loan_purpose` (tree links), `loan_product` (read-only, set by product assignment later), `requested_amount`, `tenure_months`, `repayment_frequency` (Monthly / Bi-weekly) |
  | Applicant | The person: the borrower for Individual, the authorised contact for Business. `first_name`, `middle_name`, `last_name`, `nrc`, `date_of_birth`, `position` (Business only), `phone`, `email`, `gender`, `marital_status`, `nationality` (Country). Then an Addresses panel (Frappe **Address**), **Next of Kin** (`kin_name`, `kin_relationship`, `kin_phone`, `kin_email`) and **Employment** (`employment_status`, `employment_type`, `employer_name`, `designation`, `experience_years`); both Individual only |
  | Business | Shown for Business only. `company_name`, `registration_number` (PACRA), `tpin`, `business_type`, `established_date`, `nature_of_business`, and the `directors` table |
  | Financials & Collateral | `financials` (JSON `{income, obligations, expenses}`, each a list of `{source, monthly_amount}`) and the `collaterals` table |
  | Documents | `documents` table |
  | Pre-screening | `prescreening_ruleset`, `eligibility_rule` (read-only), `monthly_income`, `monthly_obligations`, `eligible_amount`, `prescreening_data` (JSON) |
  | Appraisal | `interest_rate`, `approved_amount`, `approved_tenure_months`, `approved_frequency`, `appraisal_data` (JSON) |
  | Underwriting | `underwriting_decision`, `final_amount`, `underwriting_data` (JSON) |
  | Offer & Signing | `contract_status`, `signing_method`, `first_payment_date`, `offer_data` (JSON) |

- **`custom_status`** is the status *within* the current workflow stage (the stage itself is `workflow_state`). It replaced the four per-stage status fields (2026-10-07). The controller sets it to `Draft` on insert; whenever `workflow_state` changes it becomes `Draft`, `Approved` / `Rejected` / `Cancelled` (closed states) or `Pending` (any other stage). The hook is `validate`, because the closed states submit the document and Frappe then skips `before_save`. The stage screens set it on Save / Approve (section 7.5).
- **`credit_score`** (Int) is an application field (2026-10-07, owner's request): required for both applicant types, a whole number 300–850. The form asks for it in Employment (Individual) and in the Business step (Business). Pre-screening reads it from here; it is no longer a stage field. Older records without one can still save stage data, but editing the application asks for it.
- **`monthly_income`** (added 2026-10-07): the income verified at pre-screening. Appraisal and Offer use it for the DTI.

- **Child tables:**
  - `Custom LOS Application Director`: `full_name`, `nrc`, `phone`, `email`.
  - `Custom LOS Application Collateral`: `collateral_type` (Link **Loan Security Type**), `estimated_value`, `ownership_date`, `description`. Valuation fields: `valuation_amount`, `forced_sale_value`, `valuation_status`, `legal_status`, `valuation_details` (JSON). Co-applicant ownership was removed.
  - `Custom LOS Application Document`: `document_name`, `file`.
- **Addresses** use Frappe's `Address`, linked by Dynamic Link. `address_type` is Current (residential), Permanent or Office (registered office). The controller loads the address panel and unlinks/deletes addresses on delete.
- **Select fields** that must be chosen deliberately have a blank first option, because Frappe otherwise defaults a Select to its first option.
- **Indexes:** `stage`, `status`, `customer`, `loan_product`, `application_date`, `nrc`.
- **Design rule:** columns hold only what is filtered, sorted, summed, linked or needed for booking; the rest goes in stage JSON.
- **Not stored, calculated:** EMI, total interest, maturity date, coverage / LTV.

### 7.2 APIs (`modules/los/loan_application/api.py`)
- `create_loan_application` (POST): creates a complete application as **Draft**, stage **Application**, with its addresses. Swagger has Individual and Business examples that use real IDs.
- `update_loan_application` (PUT `?id=`): **one update for every stage modal.** Send only what changed; fields left out are kept, and `null` clears a field.
  - **Any edit** (application details or stage fields) is allowed until the application is closed (`status` Approved / Rejected / Cancelled); after that, 409. A list that is sent replaces the whole list, and the result must still be a complete application.
  - **Collaterals:** a row sent with its `row_id` is updated in place (its valuation fields are kept unless sent), a row without `row_id` is added, and a row left out is removed. A row may also carry `valuation_amount`, `forced_sale_value`, `valuation_status`, `legal_status` and `valuation_details`, which is how Underwriting saves its assets.
  - **Stage fields** can be saved at any time, with only basic type checks for now:

    | Stage | Fields |
    |---|---|
    | Any stage | `custom_status` (text, ≤ 140 characters) |
    | Pre-screening | `monthly_income`, `monthly_obligations`, `eligible_amount`, `prescreening_data` |
    | Appraisal | `approved_amount`, `approved_tenure_months`, `approved_frequency`, `interest_rate`, `appraisal_data` |
    | Underwriting | `final_amount`, `underwriting_decision`, `underwriting_data`, `collateral_valuations` |
    | Offer | `signing_method`, `contract_status`, `first_payment_date`, `offer_data` |

  - `collateral_valuations` is `[{row_id, valuation_amount, forced_sale_value, valuation_status, legal_status, valuation_details}]`. It updates existing collateral rows by `row_id` and changes only the fields that are sent.
  - **Never sent here:** `status`, `stage`, `workflow_state`, `loan_product`, `loan`, `prescreening_ruleset`, `eligibility_rule`. Stage moves go through the workflow API (section 7.4).
  - **Not built yet:** stage-specific server validation.
- `get_loan_application_by_id` (GET): the whole application, plus addresses and display names (`applicant_name`, `loan_type_name`, `product_name`, …). Child rows include `row_id`.
- `get_loan_applications` (GET):
  - One list for every stage screen. Filter by `workflow_state` (comma-separated for several, e.g. `Offer,Approved`), `custom_status`, `stage`, `status`, `applicant_type`, `channel`, `customer`, `loan_product`, and dates. Rows include `workflow_state` and `custom_status`.
  - Search covers ID, name, company, NRC and phone. Sort by modified, creation, application_date, requested_amount or name.
- `delete_loan_application` (DELETE): Draft only (409 otherwise). Its addresses go too; shared addresses are only unlinked.
- `create_loan` (POST `?id=`, 2026-10-15): converts an **Approved** application (workflow state) into a Loan through `modules/loan/loan/service.create_loan`. A new applicant gets a Customer (Individual / Company, phone, email). Carries `final_amount` (else approved, else requested), `interest_rate` (else the product rate), tenure (`approved_tenure_months`, else requested) and frequency (Bi-weekly → Bi-Weekly with 26 periods a year), and attaches the application's documents that exist as File records. Then `customer`, `loan` and stage **Booked** are set on the application (`db_set`, because the application is submitted). 400 if not Approved, 409 if a loan already exists. The Loan is created as Draft; booking and disbursement continue in the Loans module. The loan's `custom_loan_details.loan_application_number` links to the old `Custom Loan Application`, so the link is kept only on the application side (`loan`).
- **Validation:**
  - Individual needs kin, employment and a Current address. Business needs the business fields, at least 1 director and an Office address. The other applicant type's fields are cleared.
  - The tree chain must connect, be active and match the applicant type. The channel must be active. An existing customer must exist and not be disabled.
  - Amounts > 0, whole-month tenure, no future dates, text ≤ 140 characters.
  - Pipeline fields cannot be sent.
- Tested: 100/100 HTTP checks.

### 7.3 Loan Application in the frontend (stage 1, wired 2026-10-06, uncommitted)
- **List** `src/view/Origination/LoanApplication.tsx`, shared by all five stage screens (section 7.4): `get_loan_applications` with server-side search (debounced), applicant type filter, sort on ID and amount, and paging. Row actions: 👁 opens the stage's modal read-only, ✎ opens it editable (until closed), Delete (Draft only), and a ⋮ menu (View details + workflow actions). On the Loan Application screen the modal is the application form; on the stage screens it is that stage's workspace. Double-click a row = 👁. The old "Create Loan" action (old `Custom Loan Application` API) was removed.
- **Modal** `src/components/Modal/LoanApplication/`:
  - `form.ts` holds the form shape (snake_case, same names as the API), the option lists copied from the DocType selects, `buildPayload` and `valuesFromApplication`. `lookups.ts` has the dropdown hooks. `AddressFields.tsx` is the shared address block. API calls are in `src/api/LosConfiguration/LoanApplicationApi.ts`.
  - Customer & Loan: New or Existing customer (real search through `utils.search.get_customers`), applicant type, then loan type → sub-type → purpose from `get_loan_types` / `get_sub_types` / `get_purposes`. The dummy "pre-approved offers" panel was removed.
  - Individual steps: Applicant + next of kin + nationality, Residence (Current address required, Permanent optional or "Same as residential"), Employment + income / obligations (sent as `financials`; expenses are kept on edit but have no UI). Business steps: Business (with PACRA number, TPIN and Office address), Directors, Applicant (position, nationality, optional addresses). Then Collateral (Loan Security Types), Documents, Simulation, Review.
  - Documents keep the prototype's fixed tiles. Each file goes through `upload_file` (private) and is saved as `{document_name: tile label, file}`. Director files are named `Director N NRC` / `Director N Passport Photo`. On edit, existing files are kept by URL (not uploaded again), and documents with other names are sent back unchanged.
  - Simulation: requested amount, tenure and frequency are the real fields. The hardcoded product limits (e.g. 8,000 max) and the rule pills were removed because the product is only assigned later. The EMI preview still uses a placeholder 25% rate.
  - Save validates every step and jumps to the first one with errors. Create and update both send the whole application.
  - The channel is not chosen: it is always **Branch** (this app is used in branches; online sources would set their own channel).
- **View** (`LoanApplicationDetailView` + `LoanApplicationDetailParts`): reads `get_loan_application_by_id` and shows the allowed workflow actions as buttons.
- The later stage modals embed this form read-only with the real application (section 7.5).
- Not wired yet: business financials (no UI), prefilling the applicant from an existing customer, document list from Document Setup (the product isn't known at stage 1). `LoanTermsStep.tsx` and `BasicDetails.tsx` are unused prototype files that no longer type-check.
- Tested in the browser on 2026-10-06: Individual create → list → search → view → edit (amount) → delete; Business payload created and reloaded into every step; validation jumps; exact cleanup afterwards.
- Full UI pass on 2026-10-07 (Individual and Business, both through every step, plus edit, view, list filters, sort, reset / minimize / cancel, delete). Fixed: edit form refetching on window focus (lost unsaved edits); phone fields stripping "+"; negative requested amount; side summary using a different formula from the Simulation (both now use `computeSimulation` in `form.ts`); EMI label for bi-weekly; `maxLength=140` on text inputs; Business view header showing the signatory instead of the company, an empty Next of kin block, and missing PACRA / TPIN.
- Known, not fixed: uploaded files are not attached to the application (`attached_to_*` empty), so a replaced document leaves an orphan File row; `experience_years` has no upper limit (the owner's own test saved 1986).

### 7.3a Stage statuses (`custom_status`, agreed with the owner 2026-10-14)

| Stage | Statuses |
|---|---|
| Loan Application | Draft |
| Pre-screening | Pass / Fail / Review / Warning, set by the engines when the application arrives (Submit for Pre-Screening, or Return from Appraisal); officer Submit → Approved; workflow Reject → Rejected (closed) |
| Loan Appraisal | Pending → Approved |
| Underwriting | Pending → Approved (the old Approve / Conditions / Refer / Reject decision panel was removed on 2026-10-15; Return and Reject are workflow actions) |
| Offer Issuance | Pending → **Issue offer** → Offer Issued → Accepted / Rejected / Amend; contract executed + Complete → Approved; workflow Approve → Approved (closed) → **Create Loan** |

- **Pre-screening screen actions (2026-10-15):** **Save** stores the officer's edits, re-runs both engines (`evaluate_application` with `save=1`) and sets `custom_status` to the new engine status, so a case that is still a manual review stays Review. **Approve** (was "Submit") is the officer's decision: `approve=1` stores the result and sets `custom_status` = Approved. The server refuses to approve a Fail, or a Pass / Warning whose request is above the eligible amount. On Review or Warning the footer says "Approve passes it on your decision; Save keeps it as Review/Warning", and the reason includes the applicant's value (e.g. "Credit Score 614 (Review)").
- Engine verdict → status: Eligible → Pass, Eligible with Warnings → Warning, Manual Review → Review, Not Eligible → Fail (`engine.pipeline.STAGE_STATUS`). The engine result keeps the verdict wording.
- Stage lists show only `custom_status` in the Status column (the page already says which stage it is). The details page shows the stage badge and `custom_status` as Application Status.
- **Workflow gate (2026-10-15):** an application can only move **forward** out of Pre-Screening, Appraisal, Underwriting or Offer when that stage's `custom_status` is Approved. Return and Reject are always allowed, and Draft → Pre-Screening has no gate. The rule is `loan_application.service.workflow_block_reason`, registered for the doctype in `workflow/constant.ACTION_GUARDS`. `get_allowed_workflow_actions` returns each action with `blocked_reason` (null when allowed), and `process_dynamic_workflow_action` refuses a blocked action with that reason. The ⋮ menu and the details page show blocked actions disabled with the reason. It is based on the state order, so renamed actions still work.
- **Stage modal footers (2026-10-15, all four stages, shared `src/components/Modal/StageFooter.tsx`):** a status message on the left, then **Cancel**, **Save** and **Approve**. Save stores the stage data and keeps the stage open (Pre-screening: the engine status; Appraisal / Underwriting: Pending; Offer: the offer status). Approve stores it with `custom_status` Approved and is enabled only when the stage is complete: Pre-screening per the engine, Appraisal when the terms are valid, Underwriting when every asset has a type and value, is valued and legally cleared (no collateral = ready), Offer when the contract is executed. Both close the modal; moving to the next stage is still the workflow action. Underwriting lists what blocks approval under the assets, and saves `underwriting_decision` = Approved on Approve.
- **Approve from the list (Pre-Screening):** the ⋮ menu of a Pass / Warning / Review row has **Approve** (with a confirmation). It calls `evaluate_application` with `approve=1` and no overrides; the server then reuses the officer's last saved figures (`prescreening_data.engine.overrides`), so the result is the one the screen showed. The same server checks apply (no Fail, no request above the eligible amount). Other stages still approve on their screen, because they need that screen's inputs (terms, decision, signatures).
- The success message after Submit for Pre-Screening shows the engine result (`action_result.status` and eligible amount).
- The owner's chart sends Amend back to Pre-screening, Appraisal or Underwriting; the workflow today only has Return, one stage back at a time (Offer → Underwriting → Appraisal → Pre-Screening, where the engines run again). The amendment panel tells the officer to use Return. Direct routes need transitions in Workflow Configuration (backward moves are never gated).
- When an application comes back to Offer (`custom_status` Pending), the Offer screen starts a fresh offer instead of showing the old amendment.
- Contract execution no longer overwrites `custom_status` (it stays Accepted until Complete); the Offer screen's own on-screen labels are unchanged.

### 7.4 Workflow and stage screens (2026-10-07, uncommitted)
- **Frappe Workflow** "Custom LOS Loan Application Workflow" (configured in the app's Workflow Configuration screen): Draft → Pre-Screening → Appraisal → Underwriting → Offer → Approved, with Return and Reject from each stage. `update_field` is `status` (Draft / Submitted / Approved / Rejected). Approved and Rejected have `doc_status` 1, so they submit the document and lock it.
- **Moving an application** uses the generic `modules/workflow/api.py` (`get_allowed_workflow_actions`, `process_dynamic_workflow_action`), the same way as the old custom loan application. The ⋮ menu loads the allowed actions when it opens; the dialog takes an optional assignee and comment. Fixed in `modules/workflow/service.py`: a NameError after `apply_workflow`.
- **Sidebar screens** (`src/view/Origination/stages.ts`, routes in `AppRoutes.tsx`): Loan Application = `Draft` (only screen with "New"), Pre-screening = `Pre-Screening`, Loan Appraisal = `Appraisal`, Underwriting = `Underwriting`, Offer Issuance = `Offer`. Each renders `<LoanApplication stage=… />`, which always sends `workflow_state`. The Status column shows `custom_status`. Offer Issuance also lists **Approved** applications (`Offer,Approved`); their ⋮ menu has **Create Loan** (with a confirmation), or "Loan ACC-LOAN-…" once converted. Rejected applications are in no stage list.
- Stage lists and workflow actions use `staleTime: 0`, so a moved application leaves the old list straight away.

### 7.5 Stage workspaces (2026-10-07, uncommitted)
Opened from the row's ✎ (edit) or 👁 (read-only: inputs disabled, no footer). Each loads the application by id (`useStageApplication` in `src/components/Modal/stageData.tsx`), saves through `update_loan_application`, and shows the earlier stages read-only (inputs disabled) from saved data. **The modals keep the prototype's design** (owner, 2026-10-07): original footers (Cancel + Submit; Offer: Close + Complete workflow), banners and nav hints. There is no Save button: Submit / Complete stores the stage data with `custom_status` Approved (Underwriting: the decision) and closes; the Offer screen also stores each customer-response / execution change. Moving to the next stage is a separate workflow action.

| Stage | Reads | Saves |
|---|---|---|
| Pre-screening (`PrescreeningWorkspace`) | `credit_score` from the application (shown on the bureau gauge; no bureau yet); income / obligations from `financials`, else manual entry; the engine result (live preview; read-only views use the stored `prescreening_data.engine`) | `monthly_income`, `monthly_obligations`; `prescreening_data` {credit, liabilities, income, confirmed_amount, result, verdict, policy, dti, risk_score, risk_band, engine}. Submit (Eligible within the amount, or Manual Review) → `Approved`, then `evaluate_application` with save stores the engine result and `eligible_amount` (section 5.3b) |
| Appraisal (`EnrichmentWorkspace`) | `monthly_income`, `monthly_obligations`, `eligible_amount`, confirmed amount; saved `appraisal_data` | `approved_amount`, `approved_tenure_months`, `approved_frequency`, `interest_rate`; `appraisal_data` {interest_type, interest_calculation, effective_date, override_reason, charges[{name, basis, value, account, treatment}], monthly_instalment, total_repayment, projected_dti}. Approve → `Approved` |
| Underwriting (`UnderwritingWorkspace`) | `collaterals` (one asset per row), `underwriting_data`, `underwriting_decision` | `collaterals` with `row_id`: `collateral_type`, `estimated_value`, `valuation_amount`, `forced_sale_value`, `valuation_status` (Passed once there is a valuation amount and a report), `legal_status` (Passed / Pending / Unresolved), `valuation_details` (valuer, valuation, title, legal verifier, legal checks + remark, uploaded document URLs). `underwriting_decision` (Approved / Approved with Conditions / Referred / Rejected), `final_amount` (= approved amount), `underwriting_data` {notes, assignee, conditions, reason_category, reason_detail}. Submit → `custom_status` = the decision |
| Offer (`OfferWorkspace`) | Terms and charges from Appraisal, assets and legal results from Underwriting, result / risk / DTI from Pre-screening; saved `offer_data` | `signing_method` (E-signature / Physical Signature), `contract_status` (Not Generated / Signing in Progress / Executed), `first_payment_date`, `offer_data` {status (draft / pending = issued / accepted / rejected / amendment), issued_on, valid_until (+14 days), reject, amendment, signing_method, signatories [{name, role, status, signature (file URL), signed_on}], physical {dispatch, received, uploaded, verification, file_url, file_name}, executed}. `custom_status` = Pending until **Issue offer**, then Offer Issued / Accepted / Rejected / Amend, saved automatically on every response, signature or execution change; Complete → `Approved` |

- **Underwriting additions** (the prototype had no way to finish this stage): the decision panel (Approve / Conditions / Refer / Reject, built from the prototype's `DecisionButton`), and Security type + Estimated value on assets added during underwriting (needed to save them as collateral).
- **Underwriting rules:** an asset is complete when it has a valuation amount and a valuation report, its required title documents (title deed, search report) are attached and every legal check is ticked or flagged with a legal remark. "Approve / Proceed" needs every asset complete; "with Conditions" needs at least one condition; Refer / Reject need a reason. Files upload on Save (`upload_file`, private) and are uploaded once per file. Assets added in underwriting need a security type and an estimated value.
- **Charges:** Appraisal records a treatment ("Add to First Repayment" / "Billed Separately"), but the Offer screen keeps the prototype's model (owner, 2026-10-07): fees "Pre-deducted", net disbursed = amount − fees, total repayment without fees. So Appraisal's total repayment and Offer's differ when there are charges; open decision.
- **Rate and DTI cap come from the engine result** (`productTerms` in `stageData.tsx`, 2026-10-15; the hardcoded `stagePolicy` was removed): rate = saved `interest_rate`, else the product rate from `prescreening_data.engine.eligibility`; Appraisal's projected-DTI limit = the eligibility rule's max EMI-to-income ratio (else max DTI). Appraisal's rate check is 1–100% (was 18–32%, which blocked DFSL 10%, PL-002 12.5%, HOME / PL-001 17%). The approved amount defaults to the confirmed amount, else the lower of requested and eligible (it used to default to the eligible amount, approving more than the customer asked for).
- **Signing (2026-10-15):** E-signature opens a signature pad (`OfferSigning/SignaturePad.tsx`, canvas with pointer events: mouse, trackpad, touch) for each signatory; the PNG is uploaded (`signature-<application>-<role>.png`, private) and shown on the signatory card. Physical signature uploads the real signed copy (PDF / image) and links it; "Mark verified" then enables execution.
- **Known limitations:** no credit bureau (score entered manually); legal checks per asset type and the document tiles are prototype lists; the minimize / restore modal store reopens the last session; a hot reload while a modal is open can blank the page in dev (fixed by a page reload).
- **Tested in the browser on 2026-10-07** on seeded `LA-2026-00023` (Individual, vehicle): Draft → Pre-Screening (manual score, Use eligible amount, Approve) → Appraisal (charge, Save, Approve) → Underwriting (valuation + report, legal docs and checks with one flagged check, conditions, Save, reload restores everything, Submit) → Offer (accept, e-signature, both signatures, execute, Complete) → Approved; read-only earlier-stage views; Business pre-screening with manual income (`LA-2026-00027`). In-process: closed application → 409, Reject → `custom_status` Rejected, stage move → Pending. Both records were then restored exactly.
- Fixed while seeding stage data (2026-10-07): Appraisal limited tenure to 6–60 months (prototype constant), so every Home Loan and short Working Capital loan could never be submitted (now 1–360, as in the application form); Offer built the repayment schedule from today instead of Appraisal's effective date (first-payment date moved every time it was opened; bi-weekly first payment a month out); read-only views disabled their own navigation (Underwriting step tabs / Back to assets, Appraisal schedule tab, Offer summary) — now only the editable parts are disabled.
- Fixed during the test: row ⋮ menu staying open over the modal; header always saying "Prescreening"; valuation amount never saved (wrong field) and no way to confirm a valuation; legal step gated on a hidden title checklist and on documents being "Verified" (no such action), so underwriting could never be approved; mock legal values (registration details, role, licence number, pre-ticked checks); report shown as ".pdf" whatever the file; files re-uploaded on every Save; Offer pre-deducting fees and leaving them out of the total, hardcoded agreement number, disbursement channel and payroll deduction; closed-status check skipped for stage-only updates; `custom_status` not reset when the workflow submits the document.

## 8. Agreed next steps / open decisions

1. **Stage statuses (partly built).** Stage moves now run on the Frappe Workflow and the status within a stage is the single `custom_status` field (sections 7.1, 7.4, 7.5). The owner's planned per-stage statuses (Pass / Fail / Review / Warning at pre-screening, Approved / Rejected, Pending, Offer Issued, Accepted, …) are "subject to change"; the proposal below is older and kept for reference.
   - Still to build: stage-specific server validation.
   - **How the workflow runs (the owner's model):** each stage's work produces a result, but moving the application on is always a **manual decision by the user**. For example, pre-screening shows Passed or Failed, then the officer reviews and chooses Send Forward or Reject. In appraisal, the assigned user works it, marks it Complete, then sends it forward.
   - **Latest proposal (not confirmed by the owner yet):**
     - **Statuses shared by every stage:**

       | Status | Meaning |
       |---|---|
       | Pending | Arrived |
       | Returned | Sent back from a later stage |
       | In Progress | Assigned and being worked |
       | Completed | Work done, waiting for the officer's decision |
       | Forwarded | Sent to the next stage |
       | Rejected | Stopped here; overall Rejected |
       | Sent Back | Sent to an earlier stage, which becomes Returned |

     - **Actions:** `mark_complete`, `send_forward`, `reject` (reason), `send_back` (`to_stage` + reason), `reopen`.
     - **Stage results (advice for the officer, not automatic moves):**
       - Pre-screening: `prescreening_result` Passed / Failed (from the rules). This field doesn't exist yet.
       - Underwriting: the existing `underwriting_decision` (Approved / Approved with Conditions / Referred / Rejected).
     - **Application stage:** `application_status` Draft → Submitted, or Returned when sent back for correction (editable again).
     - **Offer & Signing has its own steps:** Pending → Offer Issued → Accepted / Customer Declined → Signing → Signed → Booked.
     - **Overall `status`:** Draft / In Progress / Rejected / Withdrawn / Booked.
     - **Defaults the owner may change:**
       - Send Forward on a Failed or Declined result needs an override reason.
       - Reject and Send Back are allowed from In Progress or Completed.
       - No "On Hold" status.
       - Assignment uses Frappe's Assign To.
       - No offer expiry.
   - **The server will also:** set `loan_product` with product assignment on submit, run the pre-screening and eligibility rules, and book the lending `Loan` at the end.
   - **The current DocType still has provisional options** that will change once statuses are agreed: `status` Draft / Submitted / Approved / Rejected / Cancelled; `stage` Application … Offer / Booked; plus per-stage status fields and `contract_status`.
2. **Pre-screening and eligibility engines: built 2026-10-12 (section 5.3b).** Fixed: missing facts now fail; pre-screening fields use the application's values. Still open:
   - An eligibility rule can be activated while empty.
   - Numbers like inf / NaN are accepted.
3. **Product assignment, future scope (owner agreed, build later):** block overlapping rules with a 409 on create, update and enable. Two rules overlap when they share a source and a loan type and some application can meet both conditions: turn each condition into OR-of-AND alternatives and intersect each pair per variable (number ranges, list values; whole-number variables like credit score). Run it under a lock. Today `test_rules` reports overlaps as Conflict. Ranges: use `between` with whole-number ends (700–799, then 800+) so bands don't share a boundary.
4. **Open frontend decisions (raised 2026-10-06, waiting for the owner):**
   - The Eligibility **Pre-Approval Limits** step is hardcoded demo content (tiers, amounts, sample "Medium Risk"); nothing is stored. Remove it, or define what it should store.
   - The Pre-screening **Audit** tab is always empty (no audit data from the backend). Remove it, or build a real trail. Versions already shows who published what and when.
   - When an Inactive pre-screening rule set also has a waiting draft, the ⋮ menu can only activate the draft, not switch the old version back on.
   - Product assignment settings map **Working Capital → HOME** as its default product, which looks wrong (DFSL fits better). This is the owner's data.
   - Pre-screening and eligibility status can be activated from the list without the screen's completeness checks, and the backend accepts an empty eligibility rule (item 2).
5. **Open code-review items (not fixed):**
   - No authorization (deferred).
   - Desk and `/api/resource` bypass the API's rules (DocType controllers are empty).
   - A GET → PUT round trip of the loan type setup without `include_inactive` deletes disabled nodes.
   - `send_response_list` is defined twice in `utils/api_response.py`.
6. **Smaller notes:**
   - Settings are validated as a whole. With the default `no_match` = Default Product and no default products, saving `several_match` alone gets a 400. The UI now saves the whole settings form, and disables Save until at least one default product is chosen.
7. **Other ideas raised, not decided:** short API aliases through the `override_whitelisted_methods` hook; a read-only channel list.

## 9. How to test (without touching the owner's data)

- **Real HTTP** against `http://127.0.0.1:8000` with header `Host: lms.local`:
  - Create a temporary Administrator session by inserting a `Sessions` row in code (`Session.__new__` + `insert_session_record`). Never type passwords.
  - Delete the session afterwards (DB row and `frappe.cache.hdel("session", sid)`).
- **Exact cleanup, every run:**
  - Before: snapshot table counts, `tabSeries`, the product assignment settings rows in `tabSingles`, and Loan Product `disabled` flags.
  - After: delete everything created since the test started, including `Version`, `Deleted Document`, `Comment` ("Deleted" type), `Error Log` and `Activity Log` rows. Restore the naming-series counters, the settings and the product flags. Confirm everything matches the snapshot.
- **In-process checks:** run in a transaction (`frappe.db.commit` patched to a no-op) and roll back.
- **Browser (UI) testing:** the owner logs in to the app in the browser pane. Do not put a session token into the browser yourself (blocked as a security weakening). Write tests follow the same snapshot and exact cleanup.
- **Setup data on the site (2026-10-06), all the owner's now, leave alone:**

  | Product | Pre-screening | Eligibility | Assignment rule |
  |---|---|---|---|
  | PL-001 Standard Personal Loan | `PSR-00011` Active (+ owner's draft `PSR-00013`) | `ELR-00001` Active | Branch · Personal Loan · credit score 700–800 |
  | PL-002 Standard Personal Loan2 | `PSR-00010` Active | `ELR-00003` Active (prime: bands from 650, 8× net salary at 800+, max ZMW 500k) | Branch · Personal Loan · credit score > 800 |
  | HOME HOME LOAN | `PSR-00012` Active (age 25–50, income ≥ ZMW 10k, score ≥ 650, ZMW 100k–17M, ≤ 240 months) | `ELR-00002` owner's Draft | Branch · Home Loan · no condition |
  | DFSL Diversity Financial Solutions | none | `ELR-00004` Active (business and rental income, Vehicle collateral, max ZMW 100M) | Branch · Working Capital + Agribusiness · years in business ≥ 2 and amount ≤ ZMW 100M |

  `PSR-00011`, `PSR-00012`, `ELR-00003`, `ELR-00004` and the HOME / DFSL assignment rules were seeded on 2026-10-06 at the owner's request.
- **Seeded test applications (2026-10-07, owner asked for them):** `LA-2026-00002` … `LA-2026-00046`, 45 Drafts: 3 per applicant type × loan type × sub-type, realistic Zambian data. They are test data the owner can use; `LA-2026-00001` and `LA-2026-00002` are the owner's (both moved by the owner), leave them alone.
  - **Moved through the workflow on 2026-10-07** (owner's request, real workflow actions with comments, stage data in exactly the shapes the screens save, eligibility checked with the screens' formulas; all arrive with `custom_status` Pending and a credit score):

    | Stage | Applications | Data filled |
    |---|---|---|
    | Pre-Screening | 00017, 00024, 00009, 00028, 00042 | credit score only (00042's 610 is below the business minimum) |
    | Appraisal | 00012, 00019, 00003, 00026, 00040 | + pre-screening (Pass; business income entered manually) |
    | Underwriting | 00011, 00020, 00016, 00005, 00039 | + appraisal (rates 22–26%, processing fee and other charges) |
    | Offer | 00013, 00014, 00021, 00007, 00041 | + underwriting decision (Approved / with Conditions); 00021's vehicle valued with valuer, report, title deed, search report and 6 passed legal checks (sample PDFs) |
  - **Second batch, 2026-10-07 (owner's request): `LA-2026-00047` … `00071`**, 25 new applications created through the API (with credit scores) and staged the same way, but with in-stage progress:

    | Stage | Applications and `custom_status` |
    |---|---|
    | Draft | 00047–00051 |
    | Pre-Screening | 00052, 00053 Pending; 00054 Review (eligible below requested); 00055 Pass (not yet submitted); 00056 Fail (score below minimum) |
    | Appraisal | 00057, 00058, 00060 Pending; 00059, 00061 Approved (terms done, not yet moved) |
    | Underwriting | 00062, 00066 Pending; 00063 Pending with the bike valued and legal checks done; 00064 Approved; 00065 Approved with Conditions (truck valued, two conditions) |
    | Offer | 00071 Pending; 00067 Offer Issued; 00068 Accepted; 00069 Contract Executed (e-signature, both signed); 00070 Amendment Requested (tenure, routed to Loan Appraisal; still in Offer until Return is applied) |
- **Free for tests:** only DFSL has no pre-screening rule set. Every product already has an eligibility rule and an assignment rule, so test creating those in a rolled-back transaction, or snapshot and clean up exactly. Also leave alone the Individual and Business trees and the `Branch` / `USSD` channels.
- **Last full run (2026-10-05), all with exact cleanup:**

  | Suite | Result |
  |---|---|
  | Loan application | 75/75 |
  | Setup modules (product assignment, channels, pre-screening / eligibility lifecycle, parallel-request locks, tree lookups) | 48/48 |
  | Stage updates | 43/43 |
  | In-process | 6/6 |
  | Swagger | Valid OpenAPI 3.0, 57 endpoints |

- **Test scripts live in the session scratchpad,** which is wiped every night, and the owner wants no test code in the repo. Recreate them when needed. Lint and spec validation need a scratch venv with `ruff` and `openapi-spec-validator`; ignore UP006 / UP035, since the codebase uses `typing.Dict`.
- After DocType JSON changes: `bench --site lms.local migrate`.
