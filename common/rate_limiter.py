import time
from time import sleep
import logging

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def delay(self):
        """Add delay between requests to respect rate limits"""
        current_time = time.time()
        
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests 
                        if current_time - req_time <= self.time_window]
        
        # If we've hit the rate limit, sleep until we can make another request
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.time_window - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.requests = self.requests[1:]  # Remove oldest request
        
        # Add current request
        self.requests.append(current_time)
    
    def wait(self):
        current_time = time.time()
        
        # Remove old requests
        self.requests = [t for t in self.requests if current_time - t < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (current_time - self.requests[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.requests.append(time.time())
    
    # Add this method
    def wait_if_needed(self):
        self.wait()  # This method now just calls the wait() method