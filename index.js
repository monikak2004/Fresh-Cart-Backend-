const express = require("express");
const mysql = require("mysql2");
const cors = require("cors");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");

const app = express();

/* ============================
   Config
============================ */
const PORT = 5000;
const JWT_SECRET = "freshcart_super_secret_change_me";

/* ============================
   Middleware
============================ */
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Debug
app.use((req, res, next) => {
  console.log(`➡️  ${req.method} ${req.path}`);
  next();
});

/* ============================
   DB Connection
============================ */
const db = mysql.createConnection({
  host: "localhost",
  user: "root",
  password: "20thApril2005",
  database: "freshcart_db"
});

db.connect(err => {
  if (err) {
    console.error("❌ Database connection failed:", err);
  } else {
    console.log("✅ Connected to MySQL database");
  }
});

/* ============================
   Helpers: validation
============================ */
function isValidGmail(email) {
  const re = /^[a-zA-Z0-9._%+-]+@gmail\.com$/;
  return re.test(email);
}
function isStrongPassword(pw) {
  return pw.length >= 8;
}

/* ============================
   Auth: JWT middleware
============================ */
function authenticateToken(req, res, next) {
  const header = req.headers["authorization"];
  const token = header && header.split(" ")[1];
  if (!token) return res.status(401).json({ error: "Unauthorized" });

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.status(403).json({ error: "Forbidden" });
    req.user = user;
    next();
  });
}
function authorizeRoles(...roles) {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({ error: "Insufficient privileges" });
    }
    next();
  };
}

/* ============================
   Test route
============================ */
app.get("/", (_req, res) => {
  res.send("FreshCart Backend is Running 🚀");
});

/* ============================
   Auth: REGISTER
============================ */
app.post("/register", async (req, res) => {
  try {
    const { name, email, password, role, contact_no = null, address = null } =
      req.body;

    if (!name || !email || !password || !role) {
      return res.status(400).json({ error: "All fields are required" });
    }

    if (!isValidGmail(email)) {
      return res
        .status(400)
        .json({ error: "Invalid email format (use a Gmail address)" });
    }

    if (!isStrongPassword(password)) {
      return res.status(400).json({
        error: "Password must be at least 8 characters long"
      });
    }

    db.query("SELECT user_id FROM Users WHERE email=?", [email], async (err, rows) => {
      if (err) return res.status(500).json({ error: err.sqlMessage });
      if (rows.length > 0) {
        return res.status(400).json({ error: "Email already registered" });
      }

      const hashed = await bcrypt.hash(password, 10);
      const insertSql =
        "INSERT INTO Users (name, email, password, role, contact_no, address) VALUES (?, ?, ?, ?, ?, ?)";
      db.query(
        insertSql,
        [name, email, hashed, role, contact_no, address],
        (err2, result) => {
          if (err2) return res.status(500).json({ error: err2.sqlMessage });
          res.json({
            message: "✅ User registered successfully",
            user_id: result.insertId,
            role
          });
        }
      );
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Server error" });
  }
});

/* ============================
   Auth: LOGIN (JWT)
============================ */
app.post("/login", (req, res) => {
  const { email, password } = req.body;

  if (!email || !password)
    return res.status(400).json({ error: "Email and password required" });

  const sql = "SELECT * FROM Users WHERE email = ?";
  db.query(sql, [email], async (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    if (results.length === 0)
      return res.status(401).json({ error: "Invalid email or password" });

    const user = results[0];
    const ok = await bcrypt.compare(password, user.password);
    if (!ok)
      return res.status(401).json({ error: "Invalid email or password" });

    const token = jwt.sign(
      { id: user.user_id, role: user.role },
      JWT_SECRET,
      { expiresIn: "2h" }
    );

    res.json({
      message: "✅ Login successful",
      token,
      user_id: user.user_id,
      role: user.role,
      name: user.name
    });
  });
});

/* ============================
   Example protected route
============================ */
app.get("/protected", authenticateToken, (req, res) => {
  res.json({
    message: "You accessed a protected route",
    user: req.user
  });
});

/* ============================
   Catalog (public)
============================ */
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
    if (err) return res.status(500).json({ error: err.sqlMessage });

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

/* ============================
   Place Order (shop_owner only)
============================ */
app.post(
  "/place-order",
  authenticateToken,
  authorizeRoles("shop_owner"),
  (req, res) => {
    const { user_id, variant_id, quantity } = req.body;

    if (!user_id || !variant_id || !quantity) {
      return res.status(400).json({ error: "Missing required fields" });
    }
    if (Number(user_id) !== Number(req.user.id)) {
      return res.status(403).json({ error: "Not your account" });
    }

    const priceQuery =
      "SELECT price, stock FROM Product_Variants WHERE variant_id = ?";
    db.query(priceQuery, [variant_id], (err, results) => {
      if (err) return res.status(500).json({ error: err.sqlMessage });
      if (results.length === 0)
        return res.status(404).json({ error: "Variant not found" });

      const { price, stock } = results[0];
      if (stock < quantity) {
        return res.status(400).json({ error: "Not enough stock available" });
      }

      const totalAmount = price * quantity;

      const orderQuery =
        "INSERT INTO Orders (user_id, status, payment_status, total_amount) VALUES (?, 'Pending', 'Unpaid', ?)";
      db.query(orderQuery, [user_id, totalAmount], (err2, orderResult) => {
        if (err2) return res.status(500).json({ error: err2.sqlMessage });

        const orderId = orderResult.insertId;

        const itemQuery =
          "INSERT INTO Order_Items (order_id, variant_id, quantity, price) VALUES (?, ?, ?, ?)";
        db.query(itemQuery, [orderId, variant_id, quantity, price], err3 => {
          if (err3) return res.status(500).json({ error: err3.sqlMessage });

          const paymentQuery =
            "INSERT INTO Payments (order_id, amount, status, payment_method) VALUES (?, ?, 'Pending', 'UPI')";
          db.query(paymentQuery, [orderId, totalAmount], err4 => {
            if (err4) return res.status(500).json({ error: err4.sqlMessage });

            const stockQuery =
              "UPDATE Product_Variants SET stock = stock - ? WHERE variant_id = ?";
            db.query(stockQuery, [quantity, variant_id], err5 => {
              if (err5) return res.status(500).json({ error: err5.sqlMessage });

              res.json({
                message: "✅ Order placed successfully",
                order_id: orderId,
                total: totalAmount
              });
            });
          });
        });
      });
    });
  }
);

/* ============================
   Distributor endpoints (protected)
============================ */
app.post(
  "/distributor/product",
  authenticateToken,
  authorizeRoles("distributor"),
  (req, res) => {
    const { distributor_id, subproduct_id, brand, unit, price, stock } = req.body;

    if (!distributor_id || !subproduct_id || !brand || !unit || !price || !stock) {
      return res.status(400).json({ error: "Missing required fields" });
    }
    if (Number(distributor_id) !== Number(req.user.id)) {
      return res.status(403).json({ error: "Not your account" });
    }

    const sql = `
      INSERT INTO Product_Variants (subproduct_id, distributor_id, brand, unit, price, stock)
      VALUES (?, ?, ?, ?, ?, ?)
    `;
    db.query(sql, [subproduct_id, distributor_id, brand, unit, price, stock], (err, result) => {
      if (err) return res.status(500).json({ error: err.sqlMessage });
      res.json({
        message: "✅ Product variant added successfully",
        variant_id: result.insertId
      });
    });
  }
);

app.patch(
  "/distributor/product/:variant_id",
  authenticateToken,
  authorizeRoles("distributor"),
  (req, res) => {
    const { variant_id } = req.params;
    const { price, stock } = req.body;

    if (price == null && stock == null) {
      return res.status(400).json({ error: "At least one field (price/stock) required" });
    }

    const sql = `
      UPDATE Product_Variants 
      SET price = COALESCE(?, price), stock = COALESCE(?, stock)
      WHERE variant_id = ?
    `;
    db.query(sql, [price, stock, variant_id], err => {
      if (err) return res.status(500).json({ error: err.sqlMessage });
      res.json({ message: "✅ Product variant updated successfully" });
    });
  }
);

/* ============================
   Orders + Payments (updated)
============================ */
app.get("/orders", authenticateToken, (req, res) => {
  const { user_id } = req.query;

  let sql = `
    SELECT 
      o.order_id,
      o.user_id,
      u.name AS customer_name,
      o.order_date,
      o.status,
      o.payment_status,
      o.total_amount,
      d.name AS distributor_name
    FROM Orders o
    JOIN Users u            ON o.user_id = u.user_id
    JOIN Order_Items oi     ON o.order_id = oi.order_id
    JOIN Product_Variants pv ON oi.variant_id = pv.variant_id
    JOIN Users d            ON pv.distributor_id = d.user_id
  `;

  const params = [];
  if (user_id) {
    sql += " WHERE o.user_id = ?";
    params.push(user_id);
  }

  sql += " GROUP BY o.order_id ORDER BY o.order_date DESC;";

  db.query(sql, params, (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

app.get("/order-items/:order_id", authenticateToken, (req, res) => {
  const { order_id } = req.params;
  const sql = `
    SELECT 
      oi.order_item_id,
      oi.order_id,
      oi.quantity,
      oi.price AS line_total,
      pv.variant_id,
      pv.brand,
      pv.unit,
      pv.price AS unit_price,
      sp.name AS subproduct,
      p.name  AS product,
      c.name  AS category
    FROM Order_Items oi
    JOIN Product_Variants pv ON oi.variant_id = pv.variant_id
    JOIN SubProducts      sp ON pv.subproduct_id = sp.subproduct_id
    JOIN Products         p  ON sp.product_id = p.product_id
    JOIN Categories       c  ON p.category_id = c.category_id
    WHERE oi.order_id = ?;
  `;
  db.query(sql, [order_id], (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

app.get("/payments", authenticateToken, (req, res) => {
  const { user_id } = req.query;
  let sql = `
    SELECT p.payment_id, p.order_id, p.amount, p.status, p.payment_date,
           o.user_id, u.name AS customer_name
    FROM Payments p
    JOIN Orders o ON p.order_id = o.order_id
    JOIN Users u ON o.user_id = u.user_id
  `;
  const params = [];
  if (user_id) {
    sql += " WHERE o.user_id = ?";
    params.push(user_id);
  }
  db.query(sql, params, (err, results) => {
    if (err) return res.status(500).json({ error: err.sqlMessage });
    res.json(results);
  });
});

app.patch(
  "/payments/:id",
  authenticateToken,
  authorizeRoles("distributor", "admin"),
  (req, res) => {
    const { id } = req.params;
    const { status } = req.body;
    if (!["Pending", "Paid", "Failed"].includes(status)) {
      return res.status(400).json({ error: "Invalid status" });
    }
    db.query("UPDATE Payments SET status=? WHERE payment_id=?", [status, id], err => {
      if (err) return res.status(500).json({ error: err.sqlMessage });
      res.json({ message: "✅ Payment updated successfully" });
    });
  }
);

/* ============================
   Start server
============================ */
app.listen(PORT, () => {
  console.log(`✅ Server running at http://localhost:${PORT}`);
});
