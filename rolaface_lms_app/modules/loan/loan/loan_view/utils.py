import frappe
from typing import Dict, Any, List
import json

def calculate_installment_status(row: Dict[str, Any], today) -> str:
    payment_date = frappe.utils.getdate(row.get("payment_date"))
    is_paid = row.get("is_paid", 0)
    
    if is_paid:
        return "Paid on time"
    
    if payment_date < today:
        return "Overdue"
        
    return "Upcoming"

def format_audit_timeline(versions: List[Dict], comments: List[Dict], comms: List[Dict]) -> List[Dict[str, Any]]:
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
            "details": frappe.utils.strip_html_tags(c.content or "")
        })
        
    for comm in comms:
        timeline.append({
            "id": comm.name,
            "type": "communication",
            "actor": comm.owner,
            "timestamp": comm.creation,
            "details": frappe.utils.strip_html_tags(comm.content or "")
        })
        
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


def calculate_timeline_statuses(schedule_rows: List[Dict[str, Any]], repayments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    today = frappe.utils.getdate(frappe.utils.nowdate())
    sorted_reps = sorted(repayments, key=lambda x: frappe.utils.getdate(x.get("payment_date")))
    
    unallocated_funds = 0.0
    current_rep_idx = 0
    total_reps = len(sorted_reps)
    
    for row in schedule_rows:
        due_date = frappe.utils.getdate(row.get("payment_date"))
        amount_needed = frappe.utils.flt(row.get("total_payment"))
        date_satisfied = None
        
        while amount_needed > 0 and current_rep_idx < total_reps:
            if unallocated_funds <= 0:
                rep = sorted_reps[current_rep_idx]
                unallocated_funds = (
                    frappe.utils.flt(rep.get("principal", 0)) + 
                    frappe.utils.flt(rep.get("interest", 0)) + 
                    frappe.utils.flt(rep.get("penalty", 0))
                )
                current_rep_idx += 1
            
            if unallocated_funds >= amount_needed:
                date_satisfied = frappe.utils.getdate(rep.get("payment_date"))
                unallocated_funds -= amount_needed
                amount_needed = 0
            else:
                amount_needed -= unallocated_funds
                unallocated_funds = 0
                
        if amount_needed <= 0.01:
            if date_satisfied and date_satisfied > due_date:
                row["ui_status"] = "Paid late"
            else:
                row["ui_status"] = "Paid on time"
        else:
            if due_date < today:
                row["ui_status"] = "Overdue"
            else:
                row["ui_status"] = "Upcoming"
                
        row["penalty"] = frappe.utils.flt(row.get("penalty", 0.0))

    return schedule_rows