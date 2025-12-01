const asyncHandler = require('express-async-handler');
const jwt = require('jsonwebtoken');
const User = require('../models/user');

const generateToken = (id) => {
  return jwt.sign({ id }, process.env.JWT_SECRET, {
    expiresIn: '30d',
  });
};

exports.registerUser = asyncHandler(async (req, res) => {
    const { name, email, password, role } = req.body;
    const userExists = await User.findByEmail(email);

    if (userExists) {
      res.status(400).json({ message: 'User already exists' });
    }

    const user = await User.create(name, email, password, role);

    if (user) {
      res.status(201).json({
        _id: user.insertId,
        name: name,
        email: email,
        role: role,
        token: generateToken(user.insertId),
      });
    } else {
      res.status(400).json({ message: 'Invalid user data' });
    }
});

exports.loginUser = asyncHandler(async (req, res) => {
  const { email, password } = req.body;
  const user = await User.findByEmail(email);

  if (user && (await user.matchPassword(password))) {
    res.json({
      _id: user.id,
      name: user.name,
      email: user.email,
      role: user.role,
      token: generateToken(user.id),
    });
  } else {
    res.status(401).json({ message: 'Invalid email or password' });
  }
});