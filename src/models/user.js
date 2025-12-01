const pool = require('../config/db');
const bcrypt = require('bcryptjs');

const User = {};

User.createTable = async () => {
  const sql = `
    CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      username VARCHAR(255) NOT NULL UNIQUE,
      password VARCHAR(255) NOT NULL,
      role VARCHAR(50) NOT NULL
    );
  `;
  try {
    await pool.query(sql);
    console.log('User table created or already exists.');
  } catch (err) {
    console.error('Error creating user table:', err);
  }
};

User.findByUsername = async (username) => {
  const [rows] = await pool.query('SELECT * FROM users WHERE username = ?', [username]);
  return rows[0];
};

User.create = async (username, password, role) => {
  const hashedPassword = await bcrypt.hash(password, 10);
  const sql = 'INSERT INTO users (username, password, role) VALUES (?, ?, ?)';
  const [result] = await pool.query(sql, [username, hashedPassword, role]);
  return result;
};

module.exports = User;