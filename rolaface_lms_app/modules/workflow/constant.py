ACTION_HANDLERS = {
    ("Custom LOS Loan Application", "Submit for Pre-Screening"): "rolaface_lms_app.modules.los.engine.pipeline.on_enter_prescreening",
    ("Custom LOS Loan Application", "Return"): "rolaface_lms_app.modules.los.engine.pipeline.on_enter_prescreening",
}

ACTION_GUARDS = {
    "Custom LOS Loan Application": "rolaface_lms_app.modules.los.loan_application.service.workflow_block_reason",
}
