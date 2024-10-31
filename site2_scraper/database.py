import sqlite3
import logging
from contextlib import contextmanager

class Database:
    def __init__(self, db_path="site2_scraper.db"):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Cart contents table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cart_contents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL,
                    quantity INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Product links table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS product_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Failed products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failed_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Out of stock products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS out_of_stock_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

    def save_cart_data(self, cart_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for item in cart_data:
                cursor.execute('''
                    INSERT OR REPLACE INTO cart_contents (name, price, quantity)
                    VALUES (?, ?, ?)
                ''', (item['name'], item['price'], item['quantity']))
            conn.commit()

    def get_cart_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, price, quantity FROM cart_contents')
            return [{'name': row[0], 'price': row[1], 'quantity': row[2]} 
                   for row in cursor.fetchall()]

    def save_product_links(self, products):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for product in products:
                cursor.execute('''
                    INSERT OR IGNORE INTO product_links (name, url)
                    VALUES (?, ?)
                ''', (product['name'], product['url']))
            conn.commit()

    def get_product_links(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, url FROM product_links')
            return [{'name': row[0], 'url': row[1]} for row in cursor.fetchall()]