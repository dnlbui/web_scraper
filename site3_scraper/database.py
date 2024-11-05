import sqlite3
import threading
import logging
import json
from datetime import datetime
import os


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create product_prices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS product_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    name TEXT NOT NULL,
                    base_price REAL,
                    dispensary_fee REAL,
                    currency TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url, timestamp)
                )
            ''')
            
            # Create variations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS variations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    product_name TEXT NOT NULL,
                    variation_id TEXT,
                    strength TEXT NOT NULL,
                    bottle_size TEXT,
                    display_price REAL,
                    regular_price REAL,
                    sku TEXT,
                    is_in_stock BOOLEAN,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES product_prices(id)
                )
            ''')
            
            conn.commit()

    def get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path)
        return self._local.connection

    def close(self):
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection

    def save_product_price(self, product_data):
        """Save complete product data including variations"""
        logging.info(f"Saving product data for: {product_data['url']}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('BEGIN TRANSACTION')
                
                # Insert into product_prices table
                cursor.execute('''
                    INSERT INTO product_prices 
                    (url, name, base_price, dispensary_fee, currency, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    product_data['url'],
                    product_data['name'],
                    product_data['price_info']['base_price'],
                    product_data['price_info']['dispensary_fee'],
                    product_data['price_info']['currency'],
                    product_data['timestamp']
                ))
                
                product_id = cursor.lastrowid
                
                # Insert variation data if present
                if 'variations' in product_data and product_data['variations']:
                    for variation in product_data['variations']:
                        cursor.execute('''
                            INSERT INTO variations 
                            (product_id, product_name, variation_id, strength, bottle_size,
                             display_price, regular_price, sku, is_in_stock)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            product_id,
                            product_data['name'],
                            str(variation['variation_id']),
                            variation['attributes'].get('attribute_pa_strength', ''),
                            variation['attributes'].get('attribute_pa_bottle-size', ''),
                            float(variation['display_price']),
                            float(variation['display_regular_price']),
                            variation.get('sku', ''),
                            1 if variation['is_in_stock'] else 0
                        ))
                
                conn.commit()
                logging.info(f"Successfully saved product data for: {product_data['url']}")
                
            except Exception as e:
                conn.rollback()
                logging.error(f"Error saving product data for {product_data['url']}: {str(e)}")
                logging.error("Stack trace:", exc_info=True)
                raise

    def update_variation_price(self, product_id, variation_type, variation_value, price):
        """Update price for a specific variation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE product_variations 
                SET price = ?
                WHERE product_id = ? AND variation_type = ? AND variation_value = ?
            ''', (price, product_id, variation_type, variation_value))
            conn.commit()

    def get_product_prices(self, url=None):
        """Get price history for a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if url:
                cursor.execute('''
                    SELECT name, base_price, dispensary_fee, currency, timestamp 
                    FROM product_prices 
                    WHERE url = ?
                    ORDER BY timestamp DESC
                ''', (url,))
            else:
                cursor.execute('''
                    SELECT name, base_price, dispensary_fee, currency, timestamp 
                    FROM product_prices 
                    ORDER BY timestamp DESC
                ''')
            return cursor.fetchall()

    def update_processing_status(self, url, name, status, error_message=None):
        """Update the processing status of a product"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO processing_status 
                (url, name, status, last_attempt, error_message)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            ''', (url, name, status, error_message))
            conn.commit()

    def get_pending_products(self):
        """Get products that need price updates"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT url, name FROM processing_status 
                WHERE status = 'pending'
                ORDER BY last_attempt ASC NULLS FIRST
            ''')
            return [{'url': row[0], 'name': row[1]} for row in cursor.fetchall()]

    def get_urls_from_site2_db(self):
        """Get product URLs from site2_scraper database"""
        try:
            # Get the path to the web_scraper directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            web_scraper_dir = os.path.dirname(os.path.dirname(current_dir))
            db_path = os.path.join(web_scraper_dir, 'web_scraper', 'site2_scraper.db')
            
            if not os.path.exists(db_path):
                logging.error(f"Database file not found at: {db_path}")
                return []

            logging.info(f"Attempting to connect to database at: {db_path}")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                # Enable foreign keys
                cursor.execute('PRAGMA foreign_keys = ON')
                cursor.execute('SELECT url, name FROM product_links')
                results = cursor.fetchall()
                for url, name in results:
                    logging.info(f"Found product in DB: {name} - {url}")
                urls = [row[0] for row in results]
                logging.info(f"Loaded {len(urls)} URLs from site2_scraper database")
                return urls
        except Exception as e:
            logging.error(f"Error loading URLs from site2_scraper database: {str(e)}")
            logging.error(f"Current directory: {current_dir}")
            logging.error(f"Web scraper directory: {web_scraper_dir}")
            return []
