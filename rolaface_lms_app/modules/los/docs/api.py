import frappe

from rolaface_lms_app import __version__
from rolaface_lms_app.utils.api_response import handle_api_error, send_response
from rolaface_lms_app.utils.openapi import build_spec

LOS_PACKAGES = ["rolaface_lms_app.modules.los"]
TAG_ORDER = [
	"LOS Loan Application",
	"LOS Loan Type Tree",
	"LOS Product Assignment",
	"LOS Pre-Screening",
	"LOS Eligibility",
	"LOS Document Setup",
	"LOS Channel",
	"LOS API Docs",
]
DESCRIPTION = (
	"Loan Origination: loan applications, and the setup behind them: loan type tree, product assignment, pre-screening, eligibility, document setup and channels.\n\n"
	"Built from the code on every request, so it always matches what is deployed. "
	"Click **Authorize** and paste a session ID to try the endpoints."
)


@frappe.whitelist(methods=["GET"])
def get_openapi_spec():
	"""
	OpenAPI Spec
	---
	tags:
	  - LOS API Docs
	summary: The OpenAPI 3 spec for the LOS endpoints. Powers /api-docs; also importable into Postman or Yaak.
	"""
	try:
		spec = build_spec(LOS_PACKAGES, "Rolaface LMS: LOS API", __version__, DESCRIPTION, TAG_ORDER)
		return send_response("success", "OpenAPI spec generated successfully.", spec)
	except Exception as e:
		return handle_api_error(e, "Get LOS OpenAPI Spec Error")
