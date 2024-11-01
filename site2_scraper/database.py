import sqlite3
import logging
from contextlib import contextmanager

from site2_scraper.utils import normalize_product_name

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
                    strength TEXT,
                    bottle_size TEXT,
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

            # Processing status table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_attempt DATETIME,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

    def save_cart_data(self, cart_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for item in cart_data:
                details = normalize_product_name(item['name'])
                price = float(item['price'].replace('$', '')) if isinstance(item['price'], str) else item['price']
                cursor.execute('''
                    INSERT OR REPLACE INTO cart_contents 
                    (name, price, quantity, strength, bottle_size)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    details['name'],
                    price,
                    item['quantity'],
                    details['strength'],
                    details['bottle_size']
                ))
            conn.commit()

    def get_cart_data(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, price, quantity, strength, bottle_size FROM cart_contents')
            return [{
                'name': row[0], 
                'price': row[1], 
                'quantity': row[2],
                'strength': row[3],
                'bottle_size': row[4]
            } for row in cursor.fetchall()]

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

    def get_products_by_status(self, status):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT url, name FROM processing_status 
                WHERE status = ?
                ORDER BY last_attempt ASC NULLS FIRST
            ''', (status,))
            return [{'url': row[0], 'name': row[1]} for row in cursor.fetchall()]

    def update_processing_status(self, url, name, status, error_message=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processing_status 
                (url, name, status, last_attempt, error_message)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (url, name, status, error_message))
            conn.commit()

    def mark_product_failed(self, url, name, error_message):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO failed_products 
                (url, name, error_message)
                VALUES (?, ?, ?)
            ''', (url, name, error_message))
            conn.commit()

    def mark_product_out_of_stock(self, url, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO out_of_stock_products 
                (url, name)
                VALUES (?, ?)
            ''', (url, name))
            conn.commit()