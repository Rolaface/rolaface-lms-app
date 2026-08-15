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


def calculate_timeline_statuses(schedule_rows: List[Dict[str, Any]], repayments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enriches the raw schedule rows with 'ui_status' and 'penalty' by 
    chronologically consuming actual repayment records.
    """
    today = frappe.utils.getdate(frappe.utils.nowdate())
    
    # Sort repayments chronologically to simulate the real payment timeline
    sorted_reps = sorted(repayments, key=lambda x: frappe.utils.getdate(x.get("payment_date")))
    
    # Track available unallocated funds from payments
    unallocated_funds = 0.0
    current_rep_idx = 0
    total_reps = len(sorted_reps)
    
    for row in schedule_rows:
        due_date = frappe.utils.getdate(row.get("payment_date"))
        amount_needed = frappe.utils.flt(row.get("total_payment"))
        
        # Track the date when this specific installment was fully satisfied
        date_satisfied = None
        
        # Consume unallocated funds or pull from next repayments until this installment is paid
        while amount_needed > 0 and current_rep_idx < total_reps:
            if unallocated_funds == 0:
                rep = sorted_reps[current_rep_idx]
                # Assuming 'principal' + 'interest' covers the schedule total_payment. 
                # (Adjust if your Frappe setup allocates amounts differently)
                unallocated_funds = frappe.utils.flt(rep.get("principal", 0)) + frappe.utils.flt(rep.get("interest", 0))
                current_rep_idx += 1
            
            if unallocated_funds >= amount_needed:
                # Installment is fully covered
                date_satisfied = frappe.utils.getdate(rep.get("payment_date"))
                unallocated_funds -= amount_needed
                amount_needed = 0
            else:
                # Partially covered, consume all available funds and grab the next repayment
                amount_needed -= unallocated_funds
                unallocated_funds = 0
                
        # Determine the UI Status
        if amount_needed <= 0.01: # Account for minor floating point discrepancies
            if date_satisfied and date_satisfied > due_date:
                row["ui_status"] = "Paid late"
            else:
                row["ui_status"] = "Paid on time"
        else:
            if due_date < today:
                row["ui_status"] = "Overdue"
            else:
                row["ui_status"] = "Upcoming"
                
        # The UI requires a penalty field per installment. 
        # Since standard schedule lacks this, initialize it to 0. 
        # (You can enhance this later to query Penalty Demands if used).
        row["penalty"] = 0.0

    return schedule_rows