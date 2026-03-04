// server.js
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import pkg from "pg";

dotenv.config();

const { Pool } = pkg;

// 1) CONNECT TO POSTGRES USING DATABASE_URL FROM RENDER
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// Helper for queries
async function query(text, params) {
  const res = await pool.query(text, params);
  return res;
}

// 2) ENSURE TABLES EXIST (RUNS AUTOMATICALLY ON STARTUP)
async function ensureTables() {
  // orders table
  await query(`
    CREATE TABLE IF NOT EXISTS orders (
      id SERIAL PRIMARY KEY,
      distributor_id INT NOT NULL,
      shop_owner TEXT,
      status TEXT DEFAULT 'Pending',
      amount NUMERIC(10,2),
      order_date TIMESTAMP DEFAULT NOW(),
      deleted_at TIMESTAMP
    );
  `);

  // order_items table
  await query(`
    CREATE TABLE IF NOT EXISTS order_items (
      id SERIAL PRIMARY KEY,
      order_id INT REFERENCES orders(id),
      product_name TEXT,
      quantity NUMERIC(10,2),
      unit TEXT,
      price NUMERIC(10,2),
      line_total NUMERIC(12,2)
    );
  `);

  console.log("✅ Tables ensured (orders, order_items)");
}

// 3) EXPRESS APP + ROUTES YOUR FRONTEND ALREADY CALLS
const app = express();
app.use(cors());
app.use(express.json());

// health check
app.get("/", (req, res) => {
  res.json({ ok: true, message: "Fresh Cart backend up" });
});

// Helper: fetch orders + items
async function getOrdersForDistributor(distributorId, { deleted = false } = {}) {
  const ordersRes = await query(
    `
      SELECT *
      FROM orders
      WHERE distributor_id = $1
      AND (${deleted ? "deleted_at IS NOT NULL" : "deleted_at IS NULL"})
      ORDER BY order_date DESC
    `,
    [distributorId]
  );

  const orders = ordersRes.rows;
  if (!orders.length) return [];

  const orderIds = orders.map(o => o.id);
  const itemsRes = await query(
    `SELECT * FROM order_items WHERE order_id = ANY($1::int[])`,
    [orderIds]
  );

  const itemsByOrder = itemsRes.rows.reduce((acc, item) => {
    if (!acc[item.order_id]) acc[item.order_id] = [];
    acc[item.order_id].push({
      id: item.id,
      product_name: item.product_name,
      quantity: item.quantity,
      unit: item.unit,
      price_per_unit: item.price,
      line_total: item.line_total
    });
    return acc;
  }, {});

  return orders.map(o => ({
    order_id: o.id,
    shop_owner: o.shop_owner,
    amount: o.amount,
    status: o.status,
    order_date: o.order_date,
    delete_date: o.deleted_at,
    items: itemsByOrder[o.id] || []
  }));
}

/**
 * GET /distributor/orders/:distributorId
 * active (non-deleted) orders
 */
app.get("/distributor/orders/:distributorId", async (req, res) => {
  const { distributorId } = req.params;
  try {
    const data = await getOrdersForDistributor(distributorId, { deleted: false });
    res.json(data);
  } catch (err) {
    console.error("GET orders error:", err);
    res.status(500).json({ error: "Failed to fetch orders" });
  }
});

/**
 * GET /distributor/deleted_orders/:distributorId
 * soft-deleted orders
 */
app.get("/distributor/deleted_orders/:distributorId", async (req, res) => {
  const { distributorId } = req.params;
  try {
    const data = await getOrdersForDistributor(distributorId, { deleted: true });
    res.json(data);
  } catch (err) {
    console.error("GET deleted orders error:", err);
    res.status(500).json({ error: "Failed to fetch deleted orders" });
  }
});

/**
 * PUT /distributor/update_status/:orderId
 * body: { status: "Accepted" | "Shipped" | "Out for Delivery" | "Delivered" | "Declined" }
 */
app.put("/distributor/update_status/:orderId", async (req, res) => {
  const { orderId } = req.params;
  const { status } = req.body;

  if (!status) {
    return res.status(400).json({ error: "Status is required" });
  }

  try {
    await query(
      `UPDATE orders SET status = $1 WHERE id = $2`,
      [status, orderId]
    );
    res.json({ success: true });
  } catch (err) {
    console.error("Update status error:", err);
    res.status(500).json({ error: "Failed to update status" });
  }
});

/**
 * PUT /distributor/delete_order/:orderId
 * soft delete: sets deleted_at
 */
app.put("/distributor/delete_order/:orderId", async (req, res) => {
  const { orderId } = req.params;

  try {
    await query(
      `UPDATE orders SET deleted_at = NOW() WHERE id = $1`,
      [orderId]
    );
    res.json({ success: true });
  } catch (err) {
    console.error("Delete order error:", err);
    res.status(500).json({ error: "Failed to delete order" });
  }
});

/**
 * PUT /distributor/restore_order/:orderId
 * undo soft delete
 */
app.put("/distributor/restore_order/:orderId", async (req, res) => {
  const { orderId } = req.params;

  try {
    await query(
      `UPDATE orders SET deleted_at = NULL WHERE id = $1`,
      [orderId]
    );
    res.json({ success: true });
  } catch (err) {
    console.error("Restore order error:", err);
    res.status(500).json({ error: "Failed to restore order" });
  }
});

// 4) START SERVER *AFTER* TABLES ARE READY
const PORT = process.env.PORT || 4000;

ensureTables()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`🚀 Fresh Cart backend running on port ${PORT}`);
    });
  })
  .catch(err => {
    console.error("❌ Failed to initialize database:", err);
    process.exit(1);
  });
