import threading
import time
import random
from collections import defaultdict

class LoadBalancer:
    def __init__(self, regions):
        self.regions = regions
        self.region_loads = {region: 0 for region in regions}
        self.load_threshold = 1000 
        self.lock = threading.RLock()
    
    def _simulate_network_cost(self):
        """
        TRACE-DRIVEN SIMULATION:
        Simulates 4G/LTE Edge Network Latency.
        Model: Gaussian Distribution (Mean=50ms, StdDev=15ms)
        """
        latency = random.gauss(0.050, 0.015)
        if latency < 0.010: latency = 0.010 # Floor at 10ms
        time.sleep(latency)

    def update_load(self, region, data_size):
        with self.lock:
            self.region_loads[region] += data_size
            if self.region_loads[region] > self.load_threshold:
                self._redistribute_load(region)

    def simulate_processing(self, processing_rate):
        with self.lock:
            for region in self.regions:
                self.region_loads[region] = max(0, self.region_loads[region] - processing_rate)
    
    def get_optimal_region(self):
        with self.lock:
            return min(self.region_loads.items(), key=lambda x: x[1])[0]
    
    def _redistribute_load(self, overloaded_region):
        target_region = self.get_optimal_region()
        
        if target_region != overloaded_region:
            # SIMULATE NETWORK COST
            # The system must "wait" to move data, just like real life.
            self._simulate_network_cost()
            
            transfer_amount = self.region_loads[overloaded_region] // 2
            self.region_loads[overloaded_region] -= transfer_amount
            self.region_loads[target_region] += transfer_amount