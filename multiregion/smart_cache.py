import time
from collections import OrderedDict

class SmartCache:
    def __init__(self, max_size=10, ttl=300):
        """
        max_size: Maximum number of items to keep in cache.
        ttl: Time-to-live (in seconds) for each cached item.
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key):
        """
        Retrieve cached data by key if available and not expired.
        """
        if key in self.cache:
            data, timestamp = self.cache.pop(key)
            if time.time() - timestamp < self.ttl:
                # Reinsert the item to mark it as recently used.
                self.cache[key] = (data, timestamp)
                return data
            # If expired, item is not reinserted and will be dropped.
        return None

    def set(self, key, data):
        """
        Store data in cache using the given key.
        Evict least-recently-used items if the cache is full.
        """
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (data, time.time())

    def clear(self):
        """
        Clear the entire cache.
        """
        self.cache.clear()
