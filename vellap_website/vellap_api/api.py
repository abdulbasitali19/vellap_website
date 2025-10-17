import frappe
from frappe import _
from frappe.utils.password import check_password

@frappe.whitelist(allow_guest=True)
def register_or_login(email, password):
    frappe.msgprint(f"Register or login called with email: {email}")
    """Register or login a customer user."""
    user = frappe.db.get_value("User", {"email": email})
    if not user:
        # Create new user
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "send_welcome_email": 0,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User"
        })
        new_user.insert(ignore_permissions=True)

        # Create a linked Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": new_user.first_name,
            "email_id": email
        })
        customer.insert(ignore_permissions=True)

    else:
        # Authenticate existing user
        try:
            check_password(email, password)
        except frappe.AuthenticationError:
            frappe.throw(_("Invalid password."))

    # Log user in (set session)
    frappe.local.login_manager.login_as(email)
    return {"message": "success", "redirect": "/all-products"}
