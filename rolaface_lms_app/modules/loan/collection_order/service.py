import frappe
from .utils import (create_search_filters, validate_create_payload, get_collection_orders_with_components,
                    validate_update_payload)
from .constant import GET_FIELDS

def get_collection_order(search, order_by, page, page_size):

    or_filters = None
    filters = {}
    response = {}

    if search:
           or_filters = create_search_filters(search)

    offset = (int(page) - 1) * int(page_size) 
    collection_orders = frappe.db.get_all(  'Loan Demand Offset Order', 
                                            filters=filters, or_filters=or_filters, fields=GET_FIELDS, 
                                            order_by=order_by, start=offset, page_length=int(page_size)
                                        )
    collection_orders_with_components = get_collection_orders_with_components(collection_orders)

    total_collection_orders = len(frappe.db.get_all('Loan Demand Offset Order',
                                                    filters=filters,
                                                    or_filters=or_filters,
                                                    pluck="name",
                                                ))

    total_pages = (total_collection_orders + int(page_size) - 1) // int(page_size)
    response= { 
                "collection_orders": collection_orders_with_components,
                "pagination":{
                                "page": page,
                                "page_size": page_size,
                                "total": total_collection_orders,
                                "total_pages": total_pages,
                                "has_next": int(page) < total_pages,
                                "has_prev": int(page) > 1,
                            }
                }

    return response
    
def get_collection_order_by_name(name):

    doc = frappe.get_doc('Loan Demand Offset Order', name)

    return {
            "name": doc.name,
            "title": doc.title,
            "components": doc.components
            }

def create_collection_order(payload):
    doc = frappe.new_doc('Loan Demand Offset Order')
    validate_create_payload(payload)
    doc.title = payload.get("title")
    for component in payload.get("components"):
        doc.append("components", {
            "idx": component.get("idx"),
            "demand_type": component.get("demand_type"),
        })
    doc.insert()
    return doc.title

def update_collection_order(payload):
    name = payload.get("name")

    validate_update_payload(payload)
    doc = frappe.get_doc("Loan Demand Offset Order", name)
    doc.set("components", [])
    for component in payload.get("components"):
        doc.append("components", {
            "idx": component.get("idx"),
            "demand_type": component.get("demand_type"),
        })
    doc.save()
    return doc.title