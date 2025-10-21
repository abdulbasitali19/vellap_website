import frappe
from frappe import _
from frappe.auth import LoginManager


@frappe.whitelist(allow_guest=True)
def login_customer(email, password):
    """Logs in an existing website user and ensures session + cookie consistency."""
    try:
        # Initialize and authenticate login
        login_manager = LoginManager()
        login_manager.authenticate(email, password)
        login_manager.post_login()  # Properly sets session + roles

        # Ensure session contains updated info
        frappe.local.session_obj.update({
            "user": email,
            "user_roles": frappe.get_roles(email)
        })
        frappe.db.commit()

        # Set session cookies for browser (important for navigation)
        frappe.local.cookie_manager.init_cookies()

        return {
            "status": "success",
            "message": _("Login successful."),
            "session_id": frappe.session.sid,
            "user": email,
            "redirect": "/all-products"
        }

    except Exception as e:
        frappe.log_error(message=str(e), title="Customer Login Failed")
        return {
            "status": "error",
            "message": _("Login failed. Check credentials."),
        }


@frappe.whitelist(allow_guest=True)
def register_customer(**data):
    """
    Registers a new website user as a Customer and links Address.
    Then logs them in automatically.
    """
    email = data.get("email")
    password = data.get("password")

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone = data.get("phone")
    company_name = data.get("company_name")

    address_line1 = data.get("address_line1")
    address_line2 = data.get("address_line2")
    city = data.get("city")
    postal_code = data.get("postal_code")
    country = data.get("country")

    customer_name = company_name or f"{first_name or ''} {last_name or ''}".strip()
    customer_type = "Company" if company_name else "Individual"

    # --- Check if user already exists ---
    if frappe.db.exists("User", {"email": email}):
        return {
            "status": "exists",
            "message": _("User already exists. Please log in."),
            "redirect": "login",
        }

    try:
        # 1️. Create new Website User
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name or (email.split("@")[0] if email else ""),
            "last_name": last_name,
            "mobile_no": phone,
            "send_welcome_email": 0,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User",
        })
        new_user.insert(ignore_permissions=True)

        # 2️. Create linked Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": customer_type,
            "email_id": email,
            "mobile_no": phone,
        })
        customer.insert(ignore_permissions=True)

        # 3️. Assign "Customer" Role
        if not frappe.db.exists("Has Role", {"parent": new_user.name, "role": "Customer"}):
            frappe.get_doc({
                "doctype": "Has Role",
                "parent": new_user.name,
                "parenttype": "User",
                "parentfield": "roles",
                "role": "Customer",
            }).insert(ignore_permissions=True)

        frappe.db.commit()

        # 4️. Create linked Address
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": customer_name,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "pincode": postal_code,
            "country": country,
            "phone": phone,
            "links": [
                {"link_doctype": "Customer", "link_name": customer.name},
                {"link_doctype": "User", "link_name": new_user.name},
            ],
        })
        address.insert(ignore_permissions=True)

        # 5️. Final commit and clear cache
        frappe.db.commit()
        frappe.clear_cache(user=email)

        # 6️. Auto-login newly registered customer
        return login_customer(email, password)

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=str(e), title="Customer Registration Failed")
        return {
            "status": "error",
            "message": _("Registration failed: ") + str(e),
        }
