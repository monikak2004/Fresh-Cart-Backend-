from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5500", "http://localhost:5500"], supports_credentials=True)

# ==============================
# Database Connection
# ==============================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="20thApril2005",
    database="freshcart_db"
)
cursor = db.cursor(dictionary=True)

print("✅ Flask backend running at http://127.0.0.1:5000")

# ==============================
# CORS HEADERS
# ==============================
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:5500"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response

# ==============================
# 1️⃣ ROOT
# ==============================
@app.route('/')
def home():
    return jsonify({"message": "FreshCart Flask Backend is running!"})

# ==============================
# 2️⃣ REGISTER
# ==============================
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if not all([name, email, password, role]):
        return jsonify({"error": "Missing registration details"}), 400

    cursor.execute("SELECT 1 FROM Users WHERE email=%s", (email,))
    if cursor.fetchone():
        return jsonify({"error": "User already exists"}), 400

    cursor.execute(
        "INSERT INTO Users (name, email, password, role) VALUES (%s, %s, %s, %s)",
        (name, email, password, role)
    )
    db.commit()
    return jsonify({"message": "User registered successfully"}), 201

# ==============================
# 3️⃣ LOGIN
# ==============================
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    cursor.execute("SELECT * FROM Users WHERE email=%s AND password=%s", (email, password))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "user_id": user["user_id"],
        "name": user["name"],
        "role": user["role"],
        "token": f"fake-jwt-token-{user['user_id']}",
    })

# ==============================
# 4️⃣ CATALOG
# ==============================
@app.route('/catalog', methods=['GET'])
def get_catalog():
    cursor.execute("""
        SELECT 
            c.name AS category,
            p.name AS product,
            sp.subproduct_id,
            sp.name AS subproduct,
            v.variant_id,
            v.brand,
            v.price,
            v.stock,
            v.unit,
            u.name AS distributor_name
        FROM Product_Variants v
        JOIN SubProducts sp ON v.subproduct_id = sp.subproduct_id
        JOIN Products p ON sp.product_id = p.product_id
        JOIN Categories c ON p.category_id = c.category_id
        JOIN Users u ON v.distributor_id = u.user_id
        ORDER BY c.name, p.name, sp.name, v.brand
    """)
    return jsonify(cursor.fetchall())

# ==============================
# 5️⃣ PLACE ORDER
# ==============================
@app.route('/place_order', methods=['POST'])
def place_order():
    data = request.json
    user_id = data.get("user_id")
    cart = data.get("cart", [])
    total = float(data.get("total", 0))
    delivery_fee = float(data.get("delivery_fee", 0))

    if not user_id or not cart:
        return jsonify({"error": "Missing order details"}), 400

    try:
        cursor.execute(
            "INSERT INTO Orders (user_id, status, payment_status, total_amount) VALUES (%s, %s, %s, %s)",
            (user_id, "Pending", "Unpaid", total + delivery_fee)
        )
        db.commit()
        order_id = cursor.lastrowid

        for item in cart:
            cursor.execute(
                "INSERT INTO Order_Items (order_id, variant_id, quantity, price) VALUES (%s, %s, %s, %s)",
                (order_id, item["variant_id"], item["quantity"], item["price"])
            )

        cursor.execute(
            "INSERT INTO Payments (order_id, amount, status) VALUES (%s, %s, %s)",
            (order_id, total + delivery_fee, "Pending")
        )
        db.commit()

        return jsonify({"message": "Order placed successfully", "order_id": order_id}), 201
    except Exception as e:
        db.rollback()
        print("❌ place_order error:", e)
        return jsonify({"error": str(e)}), 500

# ==============================
# 6️⃣ SHOPOWNER ORDERS
# ==============================
@app.route('/orders/<int:user_id>', methods=['GET'])
def get_orders(user_id):
    try:
        cursor.execute("""
            SELECT 
                o.order_id,
                MAX(o.status) AS status,
                MAX(o.payment_status) AS payment_status,
                MAX(o.order_date) AS order_date,
                MAX(p.amount) AS total_amount,
                MAX(p.status) AS payment_state,
                GROUP_CONCAT(DISTINCT d.name ORDER BY d.name SEPARATOR ', ') AS distributor_name
            FROM Orders o
            JOIN Payments p ON o.order_id = p.order_id
            JOIN Order_Items oi ON o.order_id = oi.order_id
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            JOIN Users d ON v.distributor_id = d.user_id
            WHERE o.user_id = %s
            GROUP BY o.order_id
            ORDER BY MAX(o.order_date) DESC
        """, (user_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ Error fetching shopowner orders:", e)
        return jsonify({"error": str(e)}), 500

# ==============================
# 7️⃣ SHOPOWNER PAYMENTS
# ==============================
@app.route('/payments/<int:user_id>', methods=['GET'])
def get_payments(user_id):
    try:
        cursor.execute("""
            SELECT 
                p.payment_id,
                p.order_id,
                p.amount,
                p.status AS payment_status,
                p.payment_method,
                p.payment_date,
                o.status AS order_status,
                u2.name AS distributor_name
            FROM Payments p
            JOIN Orders o ON p.order_id = o.order_id
            JOIN Order_Items oi ON o.order_id = oi.order_id
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            JOIN Users u2 ON v.distributor_id = u2.user_id
            WHERE o.user_id = %s
            GROUP BY p.payment_id, p.order_id, u2.name, o.status
            ORDER BY p.payment_date DESC
        """, (user_id,))
        
        payments = cursor.fetchall()
        if not payments:
            return jsonify([]), 200  # ✅ Prevent frontend crash if empty
        return jsonify(payments), 200

    except Exception as e:
        print("❌ Error fetching payments:", e)
        return jsonify({"error": "Failed to fetch payments", "details": str(e)}), 500


# ==============================
# 8️⃣ DISTRIBUTOR PAYMENTS (LIST)
# ==============================
@app.route('/distributor/payments/<int:distributor_id>', methods=['GET'])
def get_distributor_payments(distributor_id):
    try:
        cursor.execute("""
            SELECT 
                p.payment_id,
                p.order_id,
                u.name AS shop_name,
                p.amount,
                p.status AS payment_status,
                p.payment_method,
                p.payment_date
            FROM Payments p
            JOIN Orders o ON p.order_id = o.order_id
            JOIN Users u ON o.user_id = u.user_id
            JOIN Order_Items oi ON o.order_id = oi.order_id
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            WHERE v.distributor_id = %s
            GROUP BY p.payment_id
            ORDER BY p.payment_date DESC
        """, (distributor_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ Error fetching distributor payments:", e)
        return jsonify({"error": str(e)}), 500

# ==============================
# 9️⃣ DISTRIBUTOR UPDATE PAYMENT (Paid/Completed/Refunded/Cancelled)
# ==============================
@app.route('/distributor/update_payment/<int:payment_id>', methods=['PUT'])
def update_distributor_payment(payment_id):
    try:
        data = request.get_json(force=True)
        new_status = (data.get("status") or "").strip().capitalize()

        allowed_statuses = ["Pending", "Paid", "Completed", "Refunded", "Cancelled"]
        if new_status not in allowed_statuses:
            return jsonify({"error": f"Invalid status '{new_status}'"}), 400

        # ✅ Update payment in both distributor & shopowner view (same table)
        cursor.execute("""
            UPDATE Payments
            SET status = %s
            WHERE payment_id = %s
        """, (new_status, payment_id))
        db.commit()

        # ✅ Optional: update Orders.payment_status for clarity in shopowner orders view
        cursor.execute("""
            UPDATE Orders o
            JOIN Payments p ON o.order_id = p.order_id
            SET o.payment_status = p.status
            WHERE p.payment_id = %s
        """, (payment_id,))
        db.commit()

        return jsonify({"message": f"Payment #{payment_id} updated to {new_status} successfully."}), 200

    except Exception as e:
        db.rollback()
        print("❌ Error updating payment:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 🔟 DISTRIBUTOR ORDERS (LIST)
# ==============================
@app.route('/distributor/orders/<int:distributor_id>', methods=['GET'])
def get_distributor_orders(distributor_id):
    cursor.execute("""
        SELECT DISTINCT 
            o.order_id, 
            o.order_date, 
            o.status, 
            o.payment_status, 
            u.name AS shop_owner, 
            p.amount
        FROM Orders o
        JOIN Order_Items oi ON o.order_id = oi.order_id
        JOIN Product_Variants v ON oi.variant_id = v.variant_id
        JOIN Users u ON o.user_id = u.user_id
        JOIN Payments p ON o.order_id = p.order_id
        WHERE v.distributor_id = %s AND o.status != 'Deleted'
        ORDER BY o.order_date DESC
    """, (distributor_id,))
    return jsonify(cursor.fetchall())


# 1️⃣1️⃣ DISTRIBUTOR ORDER STATUS UPDATE (+ business rules)
@app.route('/distributor/update_status/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    try:
        data = request.get_json(force=True) or {}
        incoming = (data.get("status") or "").strip().lower()
        if not incoming:
            return jsonify({"error": "Missing status"}), 400

        allowed = {
            "pending": "Pending",
            "accepted": "Accepted",
            "shipped": "Shipped",
            "out for delivery": "Out for Delivery",
            "delivered": "Delivered",
            "declined": "Declined",
            "deleted": "Deleted",
        }
        if incoming not in allowed:
            return jsonify({"error": f"Invalid status: {incoming}"}), 400

        new_status = allowed[incoming]

        # Update order status
        cursor.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (new_status, order_id))
        db.commit()

        # Business rules
        if incoming == "accepted":
            # Reduce stock
            cursor.execute("SELECT variant_id, quantity FROM Order_Items WHERE order_id=%s", (order_id,))
            items = cursor.fetchall()
            for it in items:
                cursor.execute("""
                    UPDATE Product_Variants
                    SET stock = GREATEST(stock - %s, 0)
                    WHERE variant_id = %s
                """, (it["quantity"], it["variant_id"]))
            db.commit()

        elif incoming == "delivered":
            # Mark payment completed
            cursor.execute("UPDATE Payments SET status='Completed' WHERE order_id=%s", (order_id,))
            db.commit()

        elif incoming == "declined":
            cursor.execute("UPDATE Payments SET status='Cancelled' WHERE order_id=%s", (order_id,))
            db.commit()

        return jsonify({"message": f"Order #{order_id} updated to {new_status}."}), 200
    except Exception as e:
        db.rollback()
        print("❌ Error updating order:", e)
        return jsonify({"error": str(e)}), 500

# 1️⃣2️⃣ DISTRIBUTOR DELETE / RESTORE (soft delete)
@app.route('/distributor/delete_order/<int:order_id>', methods=['PUT'])
def distributor_soft_delete(order_id):
    try:
        cursor.execute("UPDATE Orders SET status='Deleted' WHERE order_id=%s", (order_id,))
        db.commit()
        return jsonify({"message": f"Order {order_id} marked as deleted."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/distributor/deleted_orders/<int:distributor_id>', methods=['GET'])
def get_deleted_orders(distributor_id):
    try:
        cursor.execute("""
            SELECT DISTINCT 
                o.order_id, o.order_date, o.status, o.payment_status,
                u.name AS shop_owner, p.amount
            FROM Orders o
            JOIN Order_Items oi ON o.order_id = oi.order_id
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            JOIN Users u ON o.user_id = u.user_id
            JOIN Payments p ON o.order_id = p.order_id
            WHERE v.distributor_id = %s AND o.status='Deleted'
            ORDER BY o.order_date DESC
        """, (distributor_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ Error fetching deleted orders:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/distributor/restore_order/<int:order_id>', methods=['PUT'])
def distributor_restore_order(order_id):
    try:
        cursor.execute("UPDATE Orders SET status='Pending' WHERE order_id=%s", (order_id,))
        db.commit()
        return jsonify({"message": f"Order {order_id} restored successfully."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

# ==============================
# 1️⃣3️⃣ USER PROFILE (GET/PUT)
# ==============================
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    cursor.execute("""
        SELECT user_id, name, email, contact_no, address, role
        FROM Users
        WHERE user_id = %s
    """, (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user), 200

@app.route('/user/<int:user_id>', methods=['PUT'])
def update_user_profile(user_id):
    data = request.get_json()
    name = data.get("name")
    contact_no = data.get("contact_no")
    address = data.get("address")

    if not name or not contact_no or not address:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        cursor.execute("""
            UPDATE Users
            SET name=%s, contact_no=%s, address=%s
            WHERE user_id=%s
        """, (name, contact_no, address, user_id))
        db.commit()
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

# ==============================
# 1️⃣4️⃣ DISTRIBUTORS LIST
# ==============================
@app.route('/distributors', methods=['GET'])
def get_distributors():
    cursor.execute("""
        SELECT 
            user_id,
            name,
            COALESCE(contact_no, '') AS contact_no,
            COALESCE(address, '') AS address
        FROM Users
        WHERE LOWER(role)='distributor'
    """)
    return jsonify(cursor.fetchall()), 200

# ==============================
# 1️⃣5️⃣ DISTRIBUTOR PRODUCTS (LIST/ADD/UPDATE/DELETE-soft)
# ==============================
@app.route('/distributor/products/<int:distributor_id>', methods=['GET'])
def get_distributor_products(distributor_id):
    try:
        cursor.execute("""
            SELECT 
                v.variant_id,
                v.brand,
                v.price,
                v.stock,
                v.unit,
                sp.name AS subproduct_name,
                p.name AS product_name,
                c.name AS category_name
            FROM Product_Variants v
            JOIN SubProducts sp ON v.subproduct_id = sp.subproduct_id
            JOIN Products p ON sp.product_id = p.product_id
            JOIN Categories c ON p.category_id = c.category_id
            WHERE v.distributor_id = %s
            ORDER BY c.name, p.name, sp.name, v.brand
        """, (distributor_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ Failed to fetch distributor products:", e)
        return jsonify({"error": "Failed to fetch products"}), 500

@app.route('/distributor/add_product', methods=['POST'])
def add_product():
    data = request.get_json(force=True)
    distributor_id = data.get("distributor_id")
    category_id = data.get("category_id")
    category_name = (data.get("category_name") or data.get("category") or "").strip()
    product_name = (data.get("product_name") or "").strip()
    subproduct_name = (data.get("subproduct_name") or "").strip()
    brand = (data.get("brand") or "").strip()
    unit = (data.get("unit") or "").strip()
    price = data.get("price")
    stock = data.get("stock")
    image_url = data.get("image_url")

    if not distributor_id or not product_name or not subproduct_name or not brand or not unit:
        return jsonify({"error": "Missing product data"}), 400
    if price is None or stock is None:
        return jsonify({"error": "Missing price/stock"}), 400

    try:
        # Resolve/insert category
        if not category_id:
            if not category_name:
                return jsonify({"error": "category_id or category_name required"}), 400
            cursor.execute("SELECT category_id FROM Categories WHERE LOWER(name)=LOWER(%s)", (category_name,))
            row = cursor.fetchone()
            if row:
                category_id = row["category_id"]
            else:
                cursor.execute("INSERT INTO Categories (name) VALUES (%s)", (category_name.capitalize(),))
                db.commit()
                category_id = cursor.lastrowid

        # Resolve/insert product
        cursor.execute("SELECT product_id FROM Products WHERE name=%s AND category_id=%s",
                       (product_name, category_id))
        p = cursor.fetchone()
        if p:
            product_id = p["product_id"]
            if image_url:
                cursor.execute("UPDATE Products SET image_url=%s WHERE product_id=%s", (image_url, product_id))
                db.commit()
        else:
            cursor.execute("INSERT INTO Products (category_id, name, image_url) VALUES (%s, %s, %s)",
                           (category_id, product_name, image_url))
            db.commit()
            product_id = cursor.lastrowid

        # Resolve/insert subproduct
        cursor.execute("SELECT subproduct_id FROM SubProducts WHERE name=%s AND product_id=%s",
                       (subproduct_name, product_id))
        sp = cursor.fetchone()
        if sp:
            subproduct_id = sp["subproduct_id"]
        else:
            cursor.execute("INSERT INTO SubProducts (product_id, name) VALUES (%s, %s)",
                           (product_id, subproduct_name))
            db.commit()
            subproduct_id = cursor.lastrowid

        # Insert variant
        cursor.execute("""
            INSERT INTO Product_Variants (subproduct_id, distributor_id, brand, unit, price, stock)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (subproduct_id, distributor_id, brand, unit, price, stock))
        db.commit()
        return jsonify({"message": "Product added successfully"}), 201
    except Exception as e:
        db.rollback()
        print("❌ Error adding product:", e)
        return jsonify({"error": "Failed to add product", "details": str(e)}), 500

@app.route('/distributor/update_product/<int:variant_id>', methods=['PUT'])
def update_distributor_product(variant_id):
    try:
        data = request.get_json(force=True)
        price = data.get("price")
        stock = data.get("stock")
        unit = data.get("unit")
        brand = data.get("brand")

        cursor.execute("""
            UPDATE Product_Variants
            SET price=%s, stock=%s, unit=%s, brand=%s
            WHERE variant_id=%s
        """, (price, stock, unit, brand, variant_id))
        db.commit()
        return jsonify({"message": f"Variant {variant_id} updated"}), 200
    except Exception as e:
        db.rollback()
        print("❌ Update product error:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/distributor/delete_product/<int:variant_id>', methods=['DELETE'])
def delete_distributor_product(variant_id):
    try:
        # Soft-delete approach to avoid FK issues (orders referencing variants)
        cursor.execute("UPDATE Product_Variants SET stock=0 WHERE variant_id=%s", (variant_id,))
        db.commit()
        return jsonify({"message": f"Variant {variant_id} marked as deleted (stock=0)."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

