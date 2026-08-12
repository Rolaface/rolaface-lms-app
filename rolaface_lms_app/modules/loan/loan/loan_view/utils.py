import frappe
from typing import Dict, Any, List
import json

def calculate_installment_status(row: Dict[str, Any], today) -> str:
    """
    Evaluates the repayment schedule row against the current date to determine UI badge state.
    """
    payment_date = frappe.utils.getdate(row.get("payment_date"))
    is_paid = row.get("is_paid", 0)
    
    if is_paid:
        return "paid" # Logic for "paid late" vs "paid on time" requires cross-referencing actual payment entries
    
    if payment_date < today:
        return "overdue"
        
    return "upcoming"

def format_audit_timeline(versions: List[Dict], comments: List[Dict], comms: List[Dict]) -> List[Dict[str, Any]]:
    """
    Normalizes three different doctypes into a single timeline schema.
    """
    timeline = []
    
    for v in versions:
        timeline.append({
            "id": v.name,
            "type": "system",
            "actor": v.owner,
            "timestamp": v.creation,
            "details": _parse_version_data(v.data)
        })
        
    for c in comments:
        timeline.append({
            "id": c.name,
            "type": "note" if c.comment_type == "Comment" else "system_note",
            "actor": c.owner,
            "timestamp": c.creation,
            "details": frappe.utils.strip_html(c.content)
        })
        
    for comm in comms:
        timeline.append({
            "id": comm.name,
            "type": "communication",
            "actor": comm.owner,
            "timestamp": comm.creation,
            "details": frappe.utils.strip_html(comm.content)
        })
        
    # Sort descending by timestamp
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    return timeline

def _parse_version_data(data_json: str) -> str:
    try:
        data = json.loads(data_json)
        changes = []
        
        if "changed" in data:
            for field in data["changed"]:
                changes.append(f"Changed {field[0]}")
                
        if "added" in data:
            for row in data["added"]:
                changes.append(f"Added row in {row[0]}")
                
        return ", ".join(changes) if changes else "Document Updated"
    except Exception:
        return "System record updated"