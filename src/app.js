// ============================
// FreshCart Backend - app.js
// ============================

const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");

const app = express();

// ============================
// Middleware
// ============================
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Debug logger
app.use((req, res, next) => {
  console.log(`➡️  ${req.method} ${req.path}`);
  console.log("   headers.content-type:", req.headers["content-type"]);
  next();
});

// ============================
// Database connection
// ============================
const db = mysql.createConnection({
  host: "localhost",
  user: "root",                // ⚡ your MySQL username
  password: "20thApril2005",   // ⚡ your MySQL password
  database: "freshcart_db"
});

db.connect(err => {
  if (err) {
    console.error("❌ Database connection failed:", err);
  } else {
    console.log("✅ Connected to MySQL database");
  }
});

// ============================
// Test Routes
// ============================
app.get("/", (req, res) => {
  res.send("FreshCart Backend is Running 🚀");
});

app.post("/echo", (req, res) => {
  console.log("📦 ECHO received body:", req.body);
  res.json({ received: req.body });
});

// ============================
// Catalog API
// ============================
app.get("/catalog", (req, res) => {
  const sql = `
    SELECT c.name AS category, 
           p.name AS product, 
           sp.name AS subproduct, 
           v.variant_id,
           v.brand, 
           v.unit, 
           v.price, 
           v.stock
    FROM Product_Variants v
    JOIN SubProducts sp ON v.subproduct_id = sp.subproduct_id
    JOIN Products p ON sp.product_id = p.product_id
    JOIN Categories c ON p.category_id = c.category_id
    ORDER BY category, product, subproduct, brand;
  `;

  db.query(sql, (err, results) => {
    if (err) {
      console.error("❌ Error fetching catalog:", err.sqlMessage);
      return res.status(500).json({ error: err.sqlMessage });
    }

    const catalog = {};
    results.forEach(row => {
      if (!catalog[row.category]) catalog[row.category] = {};
      if (!catalog[row.category][row.product]) catalog[row.category][row.product] = {};
      if (!catalog[row.category][row.product][row.subproduct]) {
        catalog[row.category][row.product][row.subproduct] = [];
      }

      catalog[row.category][row.product][row.subproduct].push({
        variant_id: row.variant_id,
        brand: row.brand,
        unit: row.unit,
        price: row.price,
        stock: row.stock
      });
    });

    res.json(catalog);
  });
});

// ============================
// Place Order API (ShopOwner)
// ============================
app.post("/place-order", (req, res) => {
  console.log("📦 Received body:", req.body);

  const { user_id, variant_id, quantity } = req.body;

  if (!user_id || !variant_id || !quantity) {
    return res.status(400).json({ error: "Missing required fields", received: req.body });
  }

  const priceQuery = "SELECT price, stock FROM Product_Variants WHERE variant_id = ?";
  db.query(priceQuery, [variant_id], (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    if (results.length === 0) return res.status(404).json({ error: "Variant not found" });

    const { price, stock } = results[0];
    if (stock < quantity) return res.status(400).json({ error: "Not enough stock available" });

    const totalAmount = price * quantity;

    // Step 1: Insert into Orders
    const orderQuery = "INSERT INTO Orders (user_id, status, payment_status, total_amount) VALUES (?, 'Pending', 'Unpaid', ?)";
    db.query(orderQuery, [user_id, totalAmount], (err, orderResult) => {
      if (err) return res.status(500).json({ error: err.sqlMessage });

      const orderId = orderResult.insertId;

      // Step 2: Insert into Order_Items
      const itemQuery = "INSERT INTO Order_Items (order_id, variant_id, quantity, price) VALUES (?, ?, ?, ?)";
      db.query(itemQuery, [orderId, variant_id, quantity, price], (err) => {
        if (err) return res.status(500).json({ error: err.sqlMessage });

        // Step 3: Insert into Payments
        const paymentQuery = "INSERT INTO Payments (order_id, amount, status, payment_method) VALUES (?, ?, 'Pending', 'UPI')";
        db.query(paymentQuery, [orderId, totalAmount], (err) => {
          if (err) return res.status(500).json({ error: err.sqlMessage });

          // Step 4: Reduce stock
          const stockQuery = "UPDATE Product_Variants SET stock = stock - ? WHERE variant_id = ?";
          db.query(stockQuery, [quantity, variant_id], (err) => {
            if (err) return res.status(500).json({ error: err.sqlMessage });

            res.json({ message: "✅ Order placed successfully", order_id: orderId, total: totalAmount });
          });
        });
      });
    });
  });
});

// ============================
// Orders API
// ============================
app.get("/orders", (req, res) => {
  const sql = `
    SELECT o.order_id, o.user_id, u.name AS customer_name, 
           o.order_date, o.status, o.payment_status, o.total_amount
    FROM Orders o
    JOIN Users u ON o.user_id = u.user_id
    ORDER BY o.order_date DESC;
  `;
  db.query(sql, (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

// ============================
// Debug Routes
// ============================
app.get("/debug/users", (req, res) => {
  db.query("SELECT * FROM Users", (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

app.get("/debug/variants", (req, res) => {
  db.query("SELECT * FROM Product_Variants", (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

// ============================
// Start Server
// ============================
const PORT = 5000;
app.listen(PORT, () => {
  console.log(`✅ Server running at http://localhost:${PORT}`);
});
