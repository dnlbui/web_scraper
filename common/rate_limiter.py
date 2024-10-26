import time
from time import sleep
import logging

class RateLimiter:
    def __init__(self, max_requests=30, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        now = time.time()
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time <= self.time_window]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.time_window - now
            if sleep_time > 0:
                logging.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
                sleep(sleep_time)
            self.requests = self.requests[1:]
        
        self.requests.append(now)