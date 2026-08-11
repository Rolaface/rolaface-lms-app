import frappe

def create_search_filters(search):
    return [
                   ["name", "like", f"%{search}%"],
                   ["title", "like", f"%{search}%"]
               ]

def validate_create_payload(payload):
    if not payload.get("title"):
        frappe.throw("Title is required")
    if not payload.get("components"):
        frappe.throw("At least one component is required")

def validate_update_payload(payload):
    if not payload.get("name"):
             raise frappe.DoesNotExistError("To update, please supply a Collection Order.")
    if not payload.get("components"):
        frappe.throw("At least one component is required")

def get_collection_orders_with_components(collection_orders):
    collection_orders_with_components = {}
    filters = {}
    if collection_orders:
        for idx, collection_order in enumerate(collection_orders):
            filters["parent"] = collection_order.name
            components = frappe.db.get_all('Loan Demand Offset Detail', filters=filters, fields=["idx", "demand_type"], order_by="idx asc")
            collection_orders_with_components[idx] = {
                                                       "name":collection_order.name,
                                                       "title": collection_order.title,
                                                       "components": components                                             
                                                    }
    return collection_orders_with_components