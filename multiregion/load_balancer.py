import threading
from collections import defaultdict

class LoadBalancer:
    def __init__(self, regions):
        self.regions = regions
        # Initialize loads for all regions to 0
        self.region_loads = {region: 0 for region in regions}
        self.load_threshold = 1000  # Configurable threshold
        self.lock = threading.Lock()
    
    def update_load(self, region, data_size):
        """Update the load for a specific region"""
        with self.lock:
            self.region_loads[region] += data_size
            if self.region_loads[region] > self.load_threshold:
                self._redistribute_load(region)
    
    def get_optimal_region(self):
        """Get the region with the lowest load"""
        with self.lock:
            return min(self.region_loads.items(), key=lambda x: x[1])[0]
    
    def _redistribute_load(self, overloaded_region):
        """Redistribute load from overloaded region"""
        target_region = self.get_optimal_region()
        if target_region != overloaded_region:
            transfer_amount = self.region_loads[overloaded_region] // 2
            self.region_loads[overloaded_region] -= transfer_amount
            self.region_loads[target_region] += transfer_amount
            print(f"Load redistributed: {transfer_amount} from {overloaded_region} to {target_region}")