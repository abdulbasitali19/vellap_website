# Copyright (c) 2025, Abdul Basit and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from erpnext.selling.doctype.quotation.quotation import _make_sales_order
from frappe.utils import add_to_date, today, date_diff
from datetime import timedelta  

class TicketAutomation(Document):
    # This class definition is standard and generally doesn't need modification
    pass

@frappe.whitelist()
def get_ticket_automation_details(doc, method):
    pass

def submit_quotations(doc):
    """Submits all associated Quotations and returns a list of submitted Quotation names."""
    submitted_quotations = []
    
    for item in doc.customer_quotations:
        quotation_name = item.quotation
        
        try:
            quotation_doc = frappe.get_doc("Quotation", quotation_name)
            
            if quotation_doc.docstatus == 1:
                submitted_quotations.append(quotation_name)
                continue

            quotation_doc.submit()
            submitted_quotations.append(quotation_name)
            frappe.msgprint(_(f"Quotation {quotation_name} submitted successfully."))
            
        except Exception as e:
            frappe.log_error(title="Quotation Submission Failed", message=str(e))
            frappe.throw(_(f"Failed to submit Quotation {quotation_name}. Error: {e}"))
            
    return submitted_quotations


def create_and_submit_sales_order(doc, submitted_quotations):
    """Creates and submits a Sales Order from submitted Quotations."""
    if not submitted_quotations:
        return None

    try:
        # We'll create one Sales Order per Quotation (you can later combine them if needed)
        created_sales_orders = []

        for quotation_name in submitted_quotations:
            # Call ERPNext's standard mapping function
            so_doc = _make_sales_order(quotation_name)
           
            today_date = frappe.utils.getdate()
        for term in so_doc.get("payment_schedule", []):
            due_date = frappe.utils.getdate(term.due_date)
            if due_date < today_date:
                term.due_date = today_date + timedelta(days=7)


            # Add any custom fields from Ticket Automation if needed
            so_doc.customer = doc.customer
            so_doc.ignore_permissions = True

            # Insert and submit the Sales Order
            so_doc.insert(ignore_permissions=True)
            so_doc.submit()

            frappe.msgprint(_(f"Sales Order {so_doc.name} created and submitted from Quotation {quotation_name}."))
            created_sales_orders.append(so_doc.name)

        # Return the first Sales Order (you can adjust to return all)
        return created_sales_orders[0] if created_sales_orders else None

    except Exception as e:
        frappe.log_error(title="Sales Order Submission Failed", message=str(e))
        frappe.throw(_(f"Failed to create/submit Sales Order. Error: {e}"))



def create_and_submit_payment_entry(doc, sales_order_name):
    """Creates and submits a Payment Entry linked to the Sales Order."""
    if not sales_order_name:
        return None

    future_date = add_to_date(today(), days=8)

    try:

        mode_of_payment = doc.mode_of_payment
        company = doc.company
        customer = doc.customer

        paid_to_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": company},
            "default_account"
        )

        if not paid_to_account:
            frappe.throw(
                _(f"No default account found for Mode of Payment '{mode_of_payment}' in company '{company}'.")
            )

        pe_doc = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "company": company,
            "party_type": "Customer",
            "party": customer,
            "posting_date": today(),
            "mode_of_payment": mode_of_payment,
            "paid_to": paid_to_account,
            "paid_amount": doc.total_amount,
            "received_amount": doc.total_amount,
            # "target_exchange_rate": 1.0,
            "reference_no": doc.invoice_reference_no,
            "reference_date": future_date,
            "references": [{
                "reference_doctype": "Sales Order",
                "reference_name": sales_order_name,
                "due_date": future_date,
                "allocated_amount": doc.total_amount
            }]
        })

        pe_doc.insert()
        pe_doc.submit()

        frappe.msgprint(_(f"Payment Entry {pe_doc.name} created and submitted."))
        return pe_doc.name

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Payment Entry Submission Failed")
        frappe.throw(_(f"Failed to create/submit Payment Entry. Error: {e}"))


# --- Core Event Hook ---

@frappe.whitelist()
def on_submit(doc, method):
    """
    Called after the Ticket Automation document is submitted.
    Executes the full sales cycle: Submit Quotations -> Create/Submit Sales Order 
    -> Create/Submit Payment Entry.
    
    Note: Transaction integrity (rollback) is implicitly handled by Frappe 
    if an exception is raised before the commit (end of the transaction).
    """
    
    frappe.msgprint(_("Starting automation of the sales cycle..."))
    
    # --- 1. Submit Quotations ---
    submitted_quotations = submit_quotations(doc)
    
    if not submitted_quotations:
        frappe.msgprint(_("No valid Quotations found to submit. Stopping cycle."))
        return
        
    # --- 2. Create and Submit Sales Order ---
    sales_order_name = create_and_submit_sales_order(doc, submitted_quotations)

    if not sales_order_name:
        frappe.msgprint(_("Sales Order could not be created/submitted. Stopping cycle."))
        return
        
    payment_entry_name = create_and_submit_payment_entry(doc, sales_order_name)
    
    frappe.msgprint(_("Sales cycle automation completed successfully."))




