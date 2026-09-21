import frappe
from typing import Dict, Any, List, Tuple, Optional
from frappe.model.workflow import apply_workflow, get_workflow_name
from frappe.desk.form.assign_to import add as add_assign, remove as remove_assign

def _get_and_validate_doc(doctype: str, docname: str) -> Tuple[Any, str]:
    """
    Internal helper to fetch a document, validate its existence, 
    prevent workflow name confusion, and verify user read permissions.
    """
    workflow_name = get_workflow_name(doctype)
    
    if docname == workflow_name:
        frappe.throw(f"Invalid docname. Please pass the actual {doctype} ID, not the Workflow name '{docname}'.")

    if not frappe.db.exists(doctype, docname):
        raise frappe.DoesNotExistError(f"{doctype} record '{docname}' not found.")

    doc = frappe.get_doc(doctype, docname)
    
    # Industry standard: Always enforce strict record-level read permissions
    doc.check_permission("read")
    
    return doc, workflow_name

def get_allowed_workflow_actions(doctype: str, docname: str) -> Dict[str, Any]:
    """
    Retrieves the current state and a list of allowed actions for the active user.
    """
    doc, workflow_name = _get_and_validate_doc(doctype, docname)
    
    if not workflow_name:
        return {"current_state": None, "allowed_actions": []}

    workflow_doc = frappe.get_doc("Workflow", workflow_name)
    state_field = workflow_doc.workflow_state_field
    current_state = doc.get(state_field)
    
    # Optimize: Convert list to a set for O(1) membership lookups
    user_roles = set(frappe.get_roles(frappe.session.user))
    allowed_actions = []

    # Build a map of state -> allow_edit
    state_edit_roles = {s.state: s.allow_edit for s in workflow_doc.get("states", [])}

    for transition in workflow_doc.get("transitions", []):
        if transition.state == current_state and transition.allowed in user_roles:
            allowed_actions.append({
                "action": transition.action,
                "next_state": transition.next_state,
                "allowed_role": transition.allowed,
                "assignable_role": state_edit_roles.get(transition.next_state)
            })

    return {
        "current_state": current_state,
        "allowed_actions": allowed_actions
    }

def clear_all_assignments(doctype: str, docname: str) -> None:
    """Removes all open ToDo assignments to ensure single-user ownership."""
    assigned_users = frappe.get_all(
        "ToDo",
        filters={"reference_type": doctype, "reference_name": docname, "status": "Open"},
        pluck="allocated_to"
    )
    
    for user in assigned_users:
        if user:
            try:
                remove_assign(doctype, docname, user)
            except Exception as e:
                # Log failures silently instead of breaking the workflow
                frappe.logger().warning(f"Failed to remove assignment for {user} on {docname}: {str(e)}")

def apply_dynamic_workflow_action(
    doctype: str, 
    docname: str, 
    action: str, 
    comment: Optional[str] = None, 
    assign_to_user: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generic processor for any workflow transition, enforcing permissions and assignments.
    """
    doc, workflow_name = _get_and_validate_doc(doctype, docname)
    
    # Enforce write permissions before altering the document
    doc.check_permission("write")
    
    if comment:
        log_text = f"Workflow Action: **{action}**\nNote: {comment}"
        if assign_to_user:
            log_text += f"\nAssigned to: {assign_to_user}"
        doc.add_comment("Comment", text=log_text)

    try:
        # Native Frappe validation against the active site's specific workflow table
        doc = apply_workflow(doc, action)
    except frappe.ValidationError as e:
        frappe.throw(f"Invalid workflow transition: {str(e)}")

    clear_all_assignments(doctype, docname)

    if assign_to_user:
        # Validate that the assignee actually has permission to view the document
        if not frappe.has_permission(doctype=doctype, ptype="read", user=assign_to_user):
            frappe.throw(f"User {assign_to_user} does not have permission to access {doctype}.")
            
        add_assign({
            "assign_to": [assign_to_user],
            "doctype": doctype,
            "name": docname,
            "description": comment or f"Document requires your attention following action: {action}"
        })
        
    workflow_doc = frappe.get_doc("Workflow", workflow_name)
    if comment:
        updated_doc.add_comment("Workflow", comment)
        
    return {
        "docname": updated_doc.name,
        "workflow_state": updated_doc.get(workflow_doc.workflow_state_field)
    }

def get_dynamic_workflow(doctype: str) -> Dict[str, Any]:
    workflow_name = frappe.db.get_value("Workflow", {"document_type": doctype}, "name")
    if not workflow_name:
        return {"workflow_name": f"{doctype} Workflow", "states": [], "transitions": [], "is_active": 0}

    doc = frappe.get_doc("Workflow", workflow_name)
    
    states = [
        {
            "state": s.state,
            "doc_status": str(s.doc_status),
            "allow_edit": s.allow_edit,
            "message": s.message or ""
        }
        for s in doc.get("states", [])
    ]
    
    transitions = [
        {
            "from_state": t.state,
            "action": t.action,
            "to_state": t.next_state,
            "allowed": t.allowed
        }
        for t in doc.get("transitions", [])
    ]
    
    return {
        "workflow_name": doc.workflow_name,
        "states": states,
        "transitions": transitions,
        "is_active": doc.is_active
    }

def save_dynamic_workflow(doctype_name: str, workflow_name: str, states: List[Dict[str, Any]], transitions: List[Dict[str, Any]], is_active: int = 1) -> str:
    state_fieldname = "workflow_state"

    # 1. Ensure Workflow State records exist
    for s in states:
        if not frappe.db.exists("Workflow State", s["state"]):
            frappe.get_doc({
                "doctype": "Workflow State",
                "workflow_state_name": s["state"]
            }).insert(ignore_permissions=True)

    # 2. Ensure Workflow Action Master records exist
    for t in transitions:
        if not frappe.db.exists("Workflow Action Master", t["action"]):
            frappe.get_doc({
                "doctype": "Workflow Action Master",
                "workflow_action_name": t["action"]
            }).insert(ignore_permissions=True)

    # 3. Ensure the custom field exists on the target Doctype
    if not frappe.db.exists("Custom Field", f"{doctype_name}-{state_fieldname}"):
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt": doctype_name,
            "fieldname": state_fieldname,
            "label": "Workflow State",
            "fieldtype": "Link",
            "options": "Workflow State",
            "insert_after": "status"
        }).insert(ignore_permissions=True)
        # Apply the schema change immediately so the workflow engine doesn't complain
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        # (It's created, but sometimes property setter / clear cache is needed)
        frappe.clear_cache(doctype=doctype_name)

    # 4. Create or Update the Workflow
    if frappe.db.exists("Workflow", workflow_name):
        doc = frappe.get_doc("Workflow", workflow_name)
    else:
        doc = frappe.new_doc("Workflow")
        doc.workflow_name = workflow_name
        doc.document_type = doctype_name
        
    doc.is_active = is_active
    doc.workflow_state_field = state_fieldname
    
    # Clear existing child tables to replace entirely
    doc.set("states", [])
    for s in states:
        doc.append("states", {
            "state": s.get("state"),
            "doc_status": s.get("doc_status", "0"),
            "allow_edit": s.get("allow_edit", "All"),
            "update_field": "",
            "update_value": "",
            "message": s.get("message", "")
        })
        
    doc.set("transitions", [])
    for t in transitions:
        # Frontend explicitly provides 'allowed'
        doc.append("transitions", {
            "state": t["from_state"],
            "action": t["action"],
            "next_state": t["to_state"],
            "allowed": t["allowed"]
        })
        
    doc.save(ignore_permissions=True)
    return doc.name