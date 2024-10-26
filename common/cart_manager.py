import queue
from threading import Lock

class CartManager:
    def __init__(self):
        self.lock = Lock()
        self.product_queue = queue.Queue()
        self.processed_products = set()

    def add_product(self, product_data):
        with self.lock:
            if product_data['url'] not in self.processed_products:
                self.product_queue.put(product_data)
                self.processed_products.add(product_data['url'])