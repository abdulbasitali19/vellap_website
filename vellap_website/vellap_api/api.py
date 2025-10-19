import frappe
from frappe import _
from frappe.utils.password import check_password
from frappe.auth import check_password



@frappe.whitelist(allow_guest=True)
def register_customer(**data):
    """Register a new customer (or log in existing one)."""

    email = data.get("email")
    password = data.get("password")

    first_name = data.get("first_name")
    last_name = data.get("last_name")
    phone = data.get("phone")

    address_line1 = data.get("address_line1")
    address_line2 = data.get("address_line2")
    city = data.get("city")
    postal_code = data.get("postal_code")
    country = data.get("country")

    # Check if user already exists
    user = frappe.db.get_value("User", {"email": email})
    if not user:
        # 1 Create new Website User
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

        # 2 Create linked Customer
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": f"{first_name} {last_name}".strip(),
            "customer_type": "Individual",
            "email_id": email,
            "mobile_no": phone
        })
        customer.insert(ignore_permissions=True)

        # 3️ Create linked Address
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": f"{first_name} {last_name}".strip(),
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "pincode": postal_code,
            "country": country,
            "phone": phone,
            "links": [
                {
                    "link_doctype": "Customer",
                    "link_name": customer.name
                }
            ]
        })
        address.insert(ignore_permissions=True)

        # Link Address to User (optional)
        address.append("links", {
            "link_doctype": "User",
            "link_name": new_user.name
        })
        address.save(ignore_permissions=True)

        return {
            "status": "success",
            "message": "Customer registered successfully.",
            "redirect": "/all-products"
            }
    else: 
        return {
            "status": "exists",
            "message": "User already exists. Please log in.",
            "redirect": "login"
        }