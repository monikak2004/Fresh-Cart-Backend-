from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import os
app = Flask(__name__)

CORS(app, origins=[
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://monikak2004.github.io"
], supports_credentials=True)

# ==============================
# Database Connection (Render Postgres)
# ==============================

db = None
cursor = None

try:
    DATABASE_URL = os.environ.get("DATABASE_URL")

    db = psycopg2.connect(DATABASE_URL)
    import psycopg2.extras
    cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    print("✅ Connected to Render PostgreSQL")



except Exception as e:
    print("❌ DB connection failed:", e)
    cursor = None
    

# ==============================
# Initialize DB schema
# ==============================
def init_db():
    if cursor is None:
        print("⚠️ Skipping DB init (no DB connection).")
        return

    try:
        print("🔧 Initializing PostgreSQL database schema...")

        # USERS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            contact_no VARCHAR(20),
            address TEXT
        )
        """)

        # CATEGORIES
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Categories (
            category_id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL
        )
        """)

        # PRODUCTS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Products (
            product_id SERIAL PRIMARY KEY,
            category_id INT REFERENCES Categories(category_id),
            name VARCHAR(100) NOT NULL,
            image_url TEXT
        )
        """)

        # SUBPRODUCTS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS SubProducts (
            subproduct_id SERIAL PRIMARY KEY,
            product_id INT REFERENCES Products(product_id),
            name VARCHAR(100) NOT NULL
        )
        """)

        # PRODUCT VARIANTS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Product_Variants (
            variant_id SERIAL PRIMARY KEY,
            subproduct_id INT REFERENCES SubProducts(subproduct_id),
            distributor_id INT REFERENCES Users(user_id),
            brand VARCHAR(100),
            unit VARCHAR(20),
            price DECIMAL,
            stock INT
        )
        """)

        # ORDERS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Orders (
            order_id SERIAL PRIMARY KEY,
            user_id INT REFERENCES Users(user_id),
            status VARCHAR(50) DEFAULT 'Pending',
            payment_status VARCHAR(50) DEFAULT 'Unpaid',
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_amount DECIMAL
        )
        """)

        # PAYMENTS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Payments (
            payment_id SERIAL PRIMARY KEY,
            order_id INT REFERENCES Orders(order_id),
            amount DECIMAL,
            status VARCHAR(50),
            payment_method VARCHAR(50),
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ORDER ITEMS
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Order_Items (
            order_item_id SERIAL PRIMARY KEY,
            order_id INT REFERENCES Orders(order_id),
            variant_id INT REFERENCES Product_Variants(variant_id),
            quantity INT,
            price DECIMAL
        )
        """)

        db.commit()
        print("✅ PostgreSQL schema initialized.")

    except Exception as e:
        db.rollback()
        print("❌ DB schema error:", e)


if cursor:
   init_db()

# ==============================
# CORS HEADERS
# ==============================
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "https://monikak2004.github.io"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response


# ==============================
# DEBUG DB
# ==============================
@app.route('/debug/db')
def debug_db():
    try:
        if cursor is None:
            return jsonify({"ok": False, "error": "DB not connected"}), 500
        cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema='public'
        """)

        tables = cursor.fetchall()
        return jsonify({"ok": True, "tables": tables}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

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
    try:
        if cursor is None:
            return jsonify({"error": "DB not connected on server"}), 500

        data = request.json or {}
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

    except Exception as e:
        print("❌ /register error:", e)
        return jsonify({"error": "Server error", "details": str(e)}), 500


# ==============================
# 3️⃣ LOGIN
# ==============================
@app.route('/login', methods=['POST'])
def login():
    try:
        db.rollback()
        if cursor is None:
            return jsonify({"error": "DB not connected on server"}), 500

        data = request.json or {}
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Missing email or password"}), 400

        cursor.execute("SELECT * FROM Users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        return jsonify({
            "user_id": user["user_id"],
            "name": user["name"],
            "role": user["role"],
            "token": f"fake-jwt-token-{user['user_id']}",
        }), 200

    except Exception as e:
        print("❌ /login error:", e)
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ==============================
# 4️⃣ CATALOG
# ==============================
@app.route('/catalog', methods=['GET'])
def get_catalog():
    try:
        db.rollback() 
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
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ /catalog error:", e)
        return jsonify({"error": "Server error", "details": str(e)}), 500


# ==============================
# 5️⃣ PLACE ORDER
# ==============================
@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        db.rollback()
        data = request.json or {}
        user_id = data.get("user_id")
        cart = data.get("cart", [])
        # we IGNORE data["total"] from the client now
        delivery_fee = float(data.get("delivery_fee", 0) or 0)

        if not user_id or not cart:
            return jsonify({"error": "Missing order details"}), 400

        # ✅ Recompute total on the backend from cart
        items_total = 0.0
        for item in cart:
            price = float(item.get("price", 0) or 0)
            qty = int(item.get("quantity", 1) or 1)
            items_total += price * qty

        order_total = items_total + delivery_fee

        # ✅ Store order_total in Orders
        cursor.execute("""
        INSERT INTO Orders (user_id, status, payment_status, total_amount)
        VALUES (%s, %s, %s, %s)
        RETURNING order_id
        """, (user_id, "Pending", "Unpaid", order_total))

        order_id = cursor.fetchone()["order_id"]
        

        # ✅ Store EACH item (keep price as unit price)
        for item in cart:
            price = float(item.get("price", 0) or 0)
            qty = int(item.get("quantity", 1) or 1)
            cursor.execute(
                "INSERT INTO Order_Items (order_id, variant_id, quantity, price) "
                "VALUES (%s, %s, %s, %s)",
                (order_id, item["variant_id"], qty, price)
            )

        # ✅ Store total payment amount (same as order_total)
        cursor.execute(
            "INSERT INTO Payments (order_id, amount, status) VALUES (%s, %s, %s)",
            (order_id, order_total, "Pending")
        )
        db.commit()

        return jsonify({
            "message": "Order placed successfully",
            "order_id": order_id,
            "items_total": round(items_total, 2),
            "delivery_fee": round(delivery_fee, 2),
            "order_total": round(order_total, 2),
        }), 201

    except Exception as e:
        db.rollback()
        print("❌ /place_order error:", e)
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ==============================
# 6️⃣ SHOPOWNER ORDERS
# ==============================
@app.route('/orders/<int:user_id>', methods=['GET'])
def get_orders(user_id):
    try:
        db.rollback()
        cursor.execute("""
            SELECT 
                o.order_id,
                o.status,
                o.payment_status,
                o.order_date,
                o.total_amount,  -- ✅ use Orders.total_amount
                MAX(p.status) AS payment_state,
                STRING_AGG(DISTINCT d.name, ', ') AS distributor_name
            FROM Orders o
            JOIN Payments p ON o.order_id = p.order_id
            JOIN Order_Items oi ON o.order_id = oi.order_id
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            JOIN Users d ON v.distributor_id = d.user_id
            WHERE o.user_id = %s
            GROUP BY o.order_id, o.status, o.payment_status, o.order_date, o.total_amount
            ORDER BY o.order_date DESC
        """, (user_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ /orders error:", e)
        return jsonify({"error": "Server error", "details": str(e)}), 500

# ==============================
# 7️⃣ SHOPOWNER PAYMENTS
# ==============================
@app.route('/payments/<int:user_id>', methods=['GET'])
def get_payments(user_id):
    try:
        db.rollback()
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
            return jsonify([]), 200
        return jsonify(payments), 200
    except Exception as e:
        print("❌ /payments error:", e)
        return jsonify({"error": "Failed to fetch payments", "details": str(e)}), 500


# ==============================
# 8️⃣ DISTRIBUTOR PAYMENTS (LIST)
# ==============================
@app.route('/distributor/payments/<int:distributor_id>', methods=['GET'])
def get_distributor_payments(distributor_id):
    try:
        db.rollback()
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
        print("❌ /distributor/payments error:", e)
        return jsonify({"error": str(e)}), 500


# ==============================
# 9️⃣ DISTRIBUTOR UPDATE PAYMENT
# ==============================
@app.route('/distributor/update_payment/<int:payment_id>', methods=['PUT'])
def update_distributor_payment(payment_id):
    try:
        db.rollback()
        data = request.get_json(force=True)

        new_status = (data.get("status") or "").strip().capitalize()

        allowed = ["Pending","Paid","Completed","Refunded","Cancelled"]

        if new_status not in allowed:
            return jsonify({"error":"Invalid status"}),400

        cursor.execute("""
        UPDATE Payments
        SET status=%s
        WHERE payment_id=%s
        """,(new_status,payment_id))

        cursor.execute("""
        UPDATE Orders o
        SET payment_status=p.status
        FROM Payments p
        WHERE o.order_id=p.order_id
        AND p.payment_id=%s
        """,(payment_id,))

        db.commit()

        return jsonify({"message":"Payment updated"}),200

    except Exception as e:
        db.rollback()
        return jsonify({"error":str(e)}),500
 

# 🔟 DISTRIBUTOR ORDERS (LIST)
@app.route('/distributor/orders/<int:distributor_id>', methods=['GET'])
def get_distributor_orders(distributor_id):
    try:
        db.rollback()
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
            LEFT JOIN Payments p ON o.order_id = p.order_id
            WHERE v.distributor_id = %s AND o.status != 'Deleted'
            ORDER BY o.order_date DESC
        """, (distributor_id,))
        return jsonify(cursor.fetchall()), 200
    except Exception as e:
        print("❌ /distributor/orders error:", e)
        return jsonify({"error": str(e)}), 500


# 1️⃣1️⃣ DISTRIBUTOR ORDER STATUS UPDATE
@app.route('/distributor/update_status/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    try:
        db.rollback()
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
        cursor.execute("UPDATE Orders SET status=%s WHERE order_id=%s", (new_status, order_id))
        db.commit()

        if incoming == "accepted":
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


# 1️⃣2️⃣ DISTRIBUTOR DELETE / RESTORE
@app.route('/distributor/delete_order/<int:order_id>', methods=['PUT'])
def distributor_soft_delete(order_id):
    try:
        db.rollback()
        cursor.execute("UPDATE Orders SET status='Deleted' WHERE order_id=%s", (order_id,))
        db.commit()
        return jsonify({"message": f"Order {order_id} marked as deleted."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/distributor/deleted_orders/<int:distributor_id>', methods=['GET'])
def get_deleted_orders(distributor_id):
    try:
        db.rollback()
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
        db.rollback()
        cursor.execute("UPDATE Orders SET status='Pending' WHERE order_id=%s", (order_id,))
        db.commit()
        return jsonify({"message": f"Order {order_id} restored successfully."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


# 1️⃣3️⃣ USER PROFILE (GET/PUT)
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    try:
        db.rollback()
        cursor.execute("""
            SELECT user_id, name, email, contact_no, address, role
            FROM Users
            WHERE user_id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/user/<int:user_id>', methods=['PUT'])
def update_user_profile(user_id):
    db.rollback()
    data = request.get_json() or {}
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


# 1️⃣4️⃣ DISTRIBUTORS LIST
@app.route('/distributors', methods=['GET'])
def get_distributors():
    try:
        db.rollback()
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 1️⃣5️⃣ DISTRIBUTOR PRODUCTS (LIST/ADD/UPDATE/DELETE-soft)
@app.route('/distributor/products/<int:distributor_id>', methods=['GET'])
def get_distributor_products(distributor_id):
    try:
        db.rollback()
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
    try:
        db.rollback()
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

        # Category
        if not category_id:
            if not category_name:
                return jsonify({"error": "category_id or category_name required"}), 400
            cursor.execute("SELECT category_id FROM Categories WHERE LOWER(name)=LOWER(%s)", (category_name,))
            row = cursor.fetchone()
            if row:
                category_id = row["category_id"]
            else:
                cursor.execute("""
                INSERT INTO Categories (name)
                VALUES (%s)
                RETURNING category_id
                """, (category_name.capitalize(),))

                category_id = cursor.fetchone()["category_id"]
                db.commit()
        # Product
        cursor.execute("SELECT product_id FROM Products WHERE name=%s AND category_id=%s",
                       (product_name, category_id))
        p = cursor.fetchone()
        if p:
            product_id = p["product_id"]
            if image_url:
                cursor.execute("UPDATE Products SET image_url=%s WHERE product_id=%s", (image_url, product_id))
                db.commit()
        else:
           cursor.execute("""
           INSERT INTO Products (category_id, name, image_url)
           VALUES (%s, %s, %s)
           RETURNING product_id
           """, (category_id, product_name, image_url))

           product_id = cursor.fetchone()["product_id"]
           db.commit()

        # Subproduct
        cursor.execute("SELECT subproduct_id FROM SubProducts WHERE name=%s AND product_id=%s",
                       (subproduct_name, product_id))
        sp = cursor.fetchone()
        if sp:
            subproduct_id = sp["subproduct_id"]
        else:
            cursor.execute("""
            INSERT INTO SubProducts (product_id, name)
            VALUES (%s, %s)
            RETURNING subproduct_id
            """, (product_id, subproduct_name))

            subproduct_id = cursor.fetchone()["subproduct_id"]
            db.commit()
 # Variant
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
        db.rollback()
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
        db.rollback()
        cursor.execute("UPDATE Product_Variants SET stock=0 WHERE variant_id=%s", (variant_id,))
        db.commit()
        return jsonify({"message": f"Variant {variant_id} marked as deleted (stock=0)."}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/order_items/<int:order_id>", methods=["GET"])
def get_order_items(order_id):
    try:
        db.rollback()
        cursor.execute("""
            SELECT 
                oi.quantity,
                oi.price,
                v.unit,
                v.brand,
                sp.name AS subproduct_name,
                p.name AS product_name
            FROM Order_Items oi
            JOIN Product_Variants v ON oi.variant_id = v.variant_id
            JOIN SubProducts sp ON v.subproduct_id = sp.subproduct_id
            JOIN Products p ON sp.product_id = p.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        rows = cursor.fetchall()

        return jsonify(rows), 200
    
    except Exception as e:
        print("❌ /order_items error:", e)
        return jsonify({"error": "Failed to fetch order items"}), 500

