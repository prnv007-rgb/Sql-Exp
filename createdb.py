import sqlite3
import os

# File for our local database
DB_NAME = "ecommerce.db"

def create_schema():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME) # Clean start
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        region TEXT,
        signup_date DATE
    )
    ''')

    # 2. Products Table
    cursor.execute('''
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT,
        price DECIMAL(10, 2)
    )
    ''')

    # 3. Orders Table (The Link)
    cursor.execute('''
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        order_date DATE,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )
    ''')

    # --- SEED DATA (To prove the joins work) ---
    users = [
        (1, 'Alice Johnson', 'alice@example.com', 'North', '2023-01-15'),
        (2, 'Bob Smith', 'bob@example.com', 'South', '2023-02-20'),
        (3, 'Charlie Brown', 'charlie@example.com', 'North', '2023-03-10')
    ]
    
    products = [
        (101, 'Laptop', 'Electronics', 1200.00),
        (102, 'Mouse', 'Electronics', 25.00),
        (103, 'Coffee Maker', 'Home', 80.00),
        (104, 'Desk Chair', 'Furniture', 150.00)
    ]

    orders = [
        (1001, 1, 101, 1, '2023-04-01'), # Alice bought Laptop
        (1002, 1, 102, 2, '2023-04-01'), # Alice bought 2 Mice
        (1003, 2, 103, 1, '2023-04-05'), # Bob bought Coffee Maker
        (1004, 3, 104, 1, '2023-04-06'), # Charlie bought Chair
        (1005, 1, 103, 1, '2023-05-10')  # Alice bought Coffee Maker later
    ]

    cursor.executemany('INSERT INTO users VALUES (?,?,?,?,?)', users)
    cursor.executemany('INSERT INTO products VALUES (?,?,?,?)', products)
    cursor.executemany('INSERT INTO orders VALUES (?,?,?,?,?)', orders)

    conn.commit()
    conn.close()
    print(f"✅ Database '{DB_NAME}' created successfully with dummy data.")

if __name__ == "__main__":
    create_schema()