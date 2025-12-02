import threading
from collections import defaultdict

class LoadBalancer:
    def __init__(self, regions):
        self.regions = regions
        # Initialize loads for all regions to 0
        self.region_loads = {region: 0 for region in regions}
        self.load_threshold = 1000  # Configurable threshold
        # CHANGE HERE: Use RLock instead of Lock to prevent deadlock
        self.lock = threading.RLock()
    
    def update_load(self, region, data_size):
        """
        Update the load for a specific region (Ingress).
        Adds data_size to the load.
        """
        with self.lock:
            self.region_loads[region] += data_size
            if self.region_loads[region] > self.load_threshold:
                self._redistribute_load(region)

    def simulate_processing(self, processing_rate):
        """
        Simulate the server processing data (Decay Logic).
        Reduces the load by 'processing_rate' for all regions, ensuring it doesn't drop below 0.
        """
        with self.lock:
            for region in self.regions:
                # Decrease load by the processing rate, but min value is 0
                self.region_loads[region] = max(0, self.region_loads[region] - processing_rate)
    
    def get_optimal_region(self):
        """Get the region with the lowest load"""
        with self.lock:
            return min(self.region_loads.items(), key=lambda x: x[1])[0]
    
    def _redistribute_load(self, overloaded_region):
        """Redistribute load from overloaded region"""
        # Because we use RLock, we can safely call get_optimal_region (which also locks)
        target_region = self.get_optimal_region()
        
        if target_region != overloaded_region:
            transfer_amount = self.region_loads[overloaded_region] // 2
            self.region_loads[overloaded_region] -= transfer_amount
            self.region_loads[target_region] += transfer_amount
            # print(f"Load redistributed: {transfer_amount} from {overloaded_region} to {target_region}")