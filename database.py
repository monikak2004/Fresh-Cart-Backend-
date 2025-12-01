import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="yourpassword",   # 🔒 Replace with your MySQL Workbench password
        database="fresh_cart"      # Replace with your DB name
    )
    return connection
