import frappe
from frappe import _
from frappe.auth import LoginManager, CookieManager
from frappe.utils.password import get_decrypted_password


def generate_api_token_for_user(user):
    """Generate (or return existing) API Key + Secret for user."""
    user_doc = frappe.get_doc("User", user)
    if not user_doc.api_key:
        user_doc.api_key = frappe.generate_hash(length=15)
    api_secret = frappe.generate_hash(length=15)
    user_doc.api_secret = api_secret
    user_doc.save(ignore_permissions=True)
    frappe.db.commit()
    return user_doc.api_key, api_secret


@frappe.whitelist(allow_guest=True)
def login_customer(email, password):
    """Authenticate user and return session + token."""
    try:
        login_manager = LoginManager()
        login_manager.authenticate(email, password)
        login_manager.post_login()

        # Generate token for API use
        api_key, api_secret = generate_api_token_for_user(email)

        # Optional: set session cookies for web usage
        cookie_mgr = CookieManager()
        cookie_mgr.init_cookies()
        cookie_mgr.set_cookie("sid", frappe.session.sid, secure=True, samesite="None")

        return {
            "status": "success",
            "message": _("Login successful."),
            "session_id": frappe.session.sid,
            "user": email,
            "api_key": api_key,
            "api_secret": api_secret,
            "redirect": "/all-products"
        }

    except Exception as e:
        frappe.log_error(message=str(e), title="Customer Login Failed")
        return {"status": "error", "message": _("Login failed. Check credentials.")}


@frappe.whitelist(allow_guest=True)
def register_customer(**data):
    """Registers new customer + creates API token."""
    email = data.get("email")
    password = data.get("password")

    if frappe.db.exists("User", {"email": email}):
        return {"status": "exists", "message": _("User already exists. Please log in."), "redirect": "login"}

    try:
        # Create user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "mobile_no": data.get("phone"),
            "send_welcome_email": 0,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User",
        })
        user.insert(ignore_permissions=True)

        # Create customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": data.get("company_name") or f"{data.get('first_name')} {data.get('last_name')}",
            "customer_type": "Company" if data.get("company_name") else "Individual",
            "customer_group" : "All Customer Groups",
            "email_id": email,
            "mobile_no": data.get("phone"),
        })
        customer.insert(ignore_permissions=True)

        # Add role
        if not frappe.db.exists("Has Role", {"parent": user.name, "role": "Customer"}):
            frappe.get_doc({
                "doctype": "Has Role",
                "parent": user.name,
                "parenttype": "User",
                "parentfield": "roles",
                "role": "Customer",
            }).insert(ignore_permissions=True)

        frappe.db.commit()

        # Create linked address
        frappe.get_doc({
            "doctype": "Address",
            "address_title": customer.customer_name,
            "address_line1": data.get("address_line1"),
            "address_line2": data.get("address_line2"),
            "city": data.get("city"),
            "pincode": data.get("postal_code"),
            "country": data.get("country"),
            "phone": data.get("phone"),
            "links": [
                {"link_doctype": "Customer", "link_name": customer.name},
                {"link_doctype": "User", "link_name": user.name},
            ],
        }).insert(ignore_permissions=True)

        frappe.db.commit()

        # Generate token immediately
        api_key, api_secret = generate_api_token_for_user(email)

        # Auto login for web session
        login_result = login_customer(email, password)
        login_result["api_key"] = api_key
        login_result["api_secret"] = api_secret
        return login_result

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(str(e), "Customer Registration Failed")
        return {"status": "error", "message": _("Registration failed: ") + str(e)}
