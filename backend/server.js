//esto es una prueba

const express = require("express");
const cors = require("cors");
const mysql = require("mysql2/promise");
require("dotenv").config();

const app = express();
app.use(cors());            
app.use(express.json());    

// Pool de conexión a MySQL
const pool = mysql.createPool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});

// Endpoint para probar que el backend vive
app.get("/api/ping", (req, res) => {
  res.json({ ok: true, message: "API Coffee Box OK" });
});

// Endpoint para crear una nueva suscripción
app.post("/api/suscripciones", async (req, res) => {
  const { planId, brands, customer } = req.body;

  if (!planId || !customer || !brands || brands.length === 0) {
    return res.status(400).json({ ok: false, error: "Datos incompletos" });
  }

  let conn;
  try {
    conn = await pool.getConnection();
    await conn.beginTransaction();

    // 1. Buscar o crear cliente por email
    const [existe] = await conn.execute(
      "SELECT id FROM customers WHERE email = ?",
      [customer.email]
    );

    let customerId;
    if (existe.length > 0) {
      customerId = existe[0].id;

      // Opcional: actualizamos datos del cliente
      await conn.execute(
        `UPDATE customers
         SET name = ?, lastname = ?, phone = ?, address = ?
         WHERE id = ?`,
        [customer.name, customer.lastname, customer.phone, customer.address, customerId]
      );
    } else {
      const [result] = await conn.execute(
        `INSERT INTO customers (name, lastname, email, phone, address)
         VALUES (?, ?, ?, ?, ?)`,
        [
          customer.name,
          customer.lastname,
          customer.email,
          customer.phone,
          customer.address,
        ]
      );
      customerId = result.insertId;
    }

    // 2. Insertar cabecera de suscripción
    const [subRes] = await conn.execute(
      `INSERT INTO subscriptions (plan_id, customer_id)
       VALUES (?, ?)`,
      [planId, customerId]
    );
    const subscriptionId = subRes.insertId;

    // 3. Insertar detalle de marcas/moliendas
    for (const item of brands) {
      await conn.execute(
        `INSERT INTO subscription_brands (subscription_id, brand_id, grind_id)
         VALUES (?, ?, ?)`,
        [subscriptionId, item.brandId, item.grindId]
      );
    }

    await conn.commit();

    res.status(201).json({
      ok: true,
      subscriptionId,
      message: "Suscripción guardada en MySQL",
    });
  } catch (err) {
    if (conn) await conn.rollback();
    console.error("Error al guardar suscripción:", err);
    // 👇 para debug (proyecto de la U no pasa nada)
    res.status(500).json({ 
      ok: false, 
      error: err.message 
    });
  } finally {
    if (conn) conn.release();
  }
});

// Endpoint para listar suscripciones (para futura página "Mis suscripciones")
app.get("/api/suscripciones", async (req, res) => {
  try {
    const [rows] = await pool.query(
      `SELECT
         s.id,
         s.created_at,
         p.name       AS plan,
         c.name       AS customer_name,
         c.lastname   AS customer_lastname,
         c.email
       FROM subscriptions s
       JOIN plans p     ON s.plan_id = p.id
       JOIN customers c ON s.customer_id = c.id
       ORDER BY s.created_at DESC`
    );

    res.json({ ok: true, data: rows });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, error: "Error al listar suscripciones" });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`API escuchando en http://localhost:${PORT}`);
});
