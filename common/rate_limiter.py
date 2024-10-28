import time
from time import sleep
import logging

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_times = []
    
    def wait(self):
        current_time = time.time()
        
        # Remove old requests
        self.request_times = [t for t in self.request_times if current_time - t < self.time_window]
        
        if len(self.request_times) >= self.max_requests:
            sleep_time = self.time_window - (current_time - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.request_times.append(time.time())
    
    # Add this method
    def wait_if_needed(self):
        self.wait()  # This method now just calls the wait() method