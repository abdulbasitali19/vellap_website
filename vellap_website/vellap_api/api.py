import frappe
from frappe import _
from frappe.auth import LoginManager


### Function 2: Login Customer


@frappe.whitelist(allow_guest=True)
def login_customer(email, password):
    """Logs in an existing user and sets the session."""
    
    try:
        login_manager = LoginManager()
        login_manager.authenticate(email, password)
        login_manager.post_login()

        # Explicitly ensure the session roles are current (for safety)
        frappe.local.session.update({"user": email, "user_roles": frappe.get_roles(email)})
        
        # Set session ID in response for client-side handling
        frappe.local.response["session_id"] = frappe.session.sid

        return {
            "status": "success",
            "message": _("Login successful."),
            "redirect": "/all-products"
        }
    
    except Exception as e:
        frappe.log_error(message=str(e), title="Customer Login Failed (Step 2)")
        return {
            "status": "error",
            "message": _("Login failed. Check credentials.")
        }


@frappe.whitelist(allow_guest=True)
def register_customer(**data):
    """
    Registers a new Customer (User, Customer Doc, Role, Address) and logs them in.
    The function ensures the user's cache is cleared to prevent 'Not Permitted' errors.
    """

    # --- Data Extraction ---
    email = data.get("email")
    password = data.get("password")
    
    # Consolidate and clean up data retrieval
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone = data.get("phone")
    company_name = data.get("company_name")
    
    address_line1 = data.get("address_line1")
    address_line2 = data.get("address_line2")
    city = data.get("city")
    postal_code = data.get("postal_code")
    country = data.get("country")
    
    customer_name = company_name or f"{first_name} {last_name}".strip()
    customer_type = "Company" if company_name else "Individual"

    # --- Check for Existing User ---
    user_name = frappe.db.get_value("User", {"email": email})
    
    if user_name: 
        return {
            "status": "exists",
            "message": _("User already exists. Please log in."),
            "redirect": "login"
        }

    # --- Create New Customer and Docs ---
    try:
        # 1. Create new Website User
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name or email.split("@")[0],
            "last_name": last_name,
            "mobile_no": phone,
            "send_welcome_email": 0,
            "enabled": 1,
            "new_password": password,
            "user_type": "Website User"
        })
        new_user.insert(ignore_permissions=True)
        
        # 2. Create linked Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": customer_type,
            "email_id": email,
            "mobile_no": phone
        })
        customer.insert(ignore_permissions=True)
        
        # 3. Assign Customer Role
        # Check is technically redundant here since it's a new user, but is good practice.
        if not frappe.db.exists("Has Role", {"parent": new_user.name, "role": "Customer"}):
            frappe.get_doc({
                "doctype": "Has Role",
                "parent": new_user.name,
                "parenttype": "User",
                "parentfield": "roles",
                "role": "Customer"
            }).insert(ignore_permissions=True)

        # CRITICAL STEP: Clear User Cache to load new roles immediately
        frappe.clear_cache(user=email) 
        
        # Commit User, Customer, and Role before attempting login
        frappe.db.commit()

        # 4. Create linked Address
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
                { "link_doctype": "Customer", "link_name": customer.name },
                { "link_doctype": "User", "link_name": new_user.name } # Link to User here
            ]
        })
        address.insert(ignore_permissions=True)
        
        # Final commit for the entire transaction
        frappe.db.commit() 
        return {
            "status": "success",
            "message": _("Registration successful."),
            "email": email,
            "password": data.get("password")
        }
        
    except Exception as e:
        # Rollback in case of error during Doc creation
        frappe.db.rollback() 
        frappe.log_error(message=str(e), title="Customer Registration Failed")
        return {
            "status": "error",
            "message": _("Registration failed: ") + str(e)
        }
