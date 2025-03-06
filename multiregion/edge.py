import os
import json
import random
import threading
import time
import pandas as pd
from datetime import datetime
from load_balancer import LoadBalancer
import zlib
from datetime import datetime

# Directories for regions
regions = ['region_1', 'region_2', 'region_3']
replicated_directories = {region: f"{region}_replicated_storage" for region in regions}
cloud_directories = {region: f"{region}_cloud_storage" for region in regions}

# Ensure directories exist
for directory in cloud_directories.values():
    os.makedirs(directory, exist_ok=True)
for directory in replicated_directories.values():
    os.makedirs(directory, exist_ok=True)

# Load balancer
load_balancer = LoadBalancer(regions)

# Simulate sensor data generation
def generate_sensor_data():
    return {
        'timestamp': pd.Timestamp.now(),
        'temperature': round(random.uniform(20.0, 30.0), 2),
        'humidity': round(random.uniform(40.0, 60.0), 2),
    }

# Edge device simulation (per region)
def edge_device(region):
    data_buffer = []
    aggregation_interval = 5  # seconds

    while True:
        # Generate new sensor data
        new_data = generate_sensor_data()
        print(f"[{region}] New sensor data: {new_data}")
        data_buffer.append(new_data)

        # Aggregate data every `aggregation_interval`
        if len(data_buffer) >= aggregation_interval:
            summary = {
                'timestamp': pd.Timestamp.now().floor('min'),
                'temperature': sum(d['temperature'] for d in data_buffer) / len(data_buffer),
                'humidity': sum(d['humidity'] for d in data_buffer) / len(data_buffer),
            }
            print(f"[{region}] Aggregated Data: {summary}")
            save_to_cloud(region, summary)
            data_buffer.clear()

        time.sleep(1)

# Custom JSON encoder class
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

# Save aggregated data to cloud storage
def save_to_cloud(region, data):
    file_name = f"aggregated_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.json.gz"
    
    # Compress and get data size
    json_data = json.dumps(data, cls=DateTimeEncoder)
    compressed_data = zlib.compress(json_data.encode('utf-8'))
    data_size = len(compressed_data)
    
    # Get optimal region before updating load
    current_load = load_balancer.region_loads[region]
    optimal_region = load_balancer.get_optimal_region()
    
    # Only redirect if the optimal region has significantly less load
    if optimal_region != region and load_balancer.region_loads[optimal_region] < current_load * 0.7:
        print(f"Redirecting data from {region} to {optimal_region} for better load distribution")
        region = optimal_region
    
    file_path = os.path.join(cloud_directories[region], file_name)
    
    # Save compressed data
    with open(file_path, 'wb') as f:
        f.write(compressed_data)
    
    compression_ratio = (len(json_data.encode('utf-8')) - len(compressed_data)) / len(json_data.encode('utf-8')) * 100
    print(f"Compression ratio: {compression_ratio:.2f}%")
    print(f"Current loads: {load_balancer.region_loads}")
    
    # Update load balancer
    load_balancer.update_load(region, data_size)

# Inter-region replication
def replicate_data(source_region, target_region):
    source_dir = cloud_directories[source_region]
    target_dir = replicated_directories[target_region]

    while True:
        for file_name in os.listdir(source_dir):
            source_file = os.path.join(source_dir, file_name)
            target_file = os.path.join(target_dir, file_name)

            if not os.path.exists(target_file):
                print(f"Replicating {file_name} from {source_region} to {target_region}")
                try:
                    with open(source_file, 'rb') as src, open(target_file, 'wb') as tgt:
                        tgt.write(src.read())
                except Exception as e:
                    print(f"Error replicating file {file_name}: {str(e)}")
        time.sleep(5)

# Read compressed data from file
def read_compressed_data(file_path):
    try:
        with open(file_path, 'rb') as f:
            compressed_data = f.read()
            json_data = zlib.decompress(compressed_data).decode('utf-8')
            return json.loads(json_data)
    except Exception as e:
        print(f"Error reading compressed file {file_path}: {str(e)}")
        return None

# Start the simulation
def main():
    # Start edge devices for each region
    for region in regions:
        threading.Thread(target=edge_device, args=(region,), daemon=True).start()

    # Start inter-region replication threads
    for i, source_region in enumerate(regions):
        target_region = regions[(i + 1) % len(regions)]  # Circular replication
        threading.Thread(target=replicate_data, args=(source_region, target_region), daemon=True).start()

    # Keep the main thread alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()




'''
What We Implemented
1) Simulated Sensor Data Generation:

The system generates synthetic sensor data at regular intervals, mimicking the behavior of IoT sensors.

2) Edge Device Pre-Processing:

Instead of sending raw data to the cloud, the edge device aggregates the data periodically. This reduces the size and frequency of data uploads to the cloud.

3) Cloud Storage Simulation:

Aggregated data is stored in a simulated "cloud_storage" directory, representing data transfer to the cloud.

4) Replication for Reliability:

A replication mechanism ensures that aggregated data is copied to a "replicated_storage" directory. This step models inter-region replication strategies in cloud services.

5) Error Handling:

We implemented robust mechanisms to handle invalid or corrupted files, simulating real-world challenges when processing cloud-stored data.
'''


'''
concept we've implemented builds on existing cloud-based solutions but offers a new perspective or an alternative to solving common cost 
and bandwidth inefficiencies in cloud computing, especially around data transfer and egress fees.
'''



'''
1) Reducing Egress Costs
Problem: Cloud providers often charge high fees for data that is transferred out of their infrastructure, especially across regions. Sending raw data continuously from the edge devices to the cloud can lead to unnecessary high egress costs.

Traditional Solutions: Many solutions aggregate data at the edge, but the critical issue is how to efficiently aggregate and minimize what is sent to the cloud, especially in the context of multi-region systems.

New Approach (The Loophole Fix):

Edge Aggregation and Replication: Instead of sending each individual sensor reading to the cloud, which incurs egress costs, we aggregate multiple readings locally at the edge (using edge devices) and send only aggregated data to the cloud. This dramatically reduces the volume of data being transferred.
We also simulate multi-region data replication, meaning that if one region needs to access this data, it can do so locally, reducing the need for inter-region data egress. By replicating aggregated data only and not raw sensor readings, we avoid repeated large transfers between regions, which would typically add to costs.
Impact:

We can optimize the data flow and minimize the overall data egress to the cloud, especially in cases where only summary information is needed in the cloud (instead of raw data), which results in cost savings.

2. Bandwidth Optimization
Problem: The traditional cloud model requires transferring large amounts of data, which can be inefficient when dealing with high-frequency sensor data. This also puts a strain on network bandwidth and increases latency, especially in IoT and edge computing scenarios.

Traditional Solutions: Some solutions aggregate data at the edge, but the major question is how much data should be aggregated, how often, and whether it’s sent in batches or as an ongoing stream.

New Approach:

In the simulation, the aggregation happens at the edge where data from sensors is collected and processed in real-time. The aggregated data is sent to the cloud only when necessary. This prevents continuous bandwidth consumption for sending real-time sensor data.
By implementing multi-region replication, we ensure that data is available locally in regions that need it, rather than always relying on a central region to serve that data. This setup ensures the efficient use of network resources and ensures faster access to the aggregated data from local regions, improving bandwidth performance.
Impact:

This approach ensures that the network is not overloaded by sending large amounts of raw data. Only summary data or changes are transferred, making the entire system more efficient in terms of both bandwidth and cost.

3. Multi-Region Resilience and Fault Tolerance
Problem: Cloud systems often rely on centralized data, and if that data becomes inaccessible (due to network issues, region failure, etc.), it can lead to system downtime or slowdowns.

Traditional Solutions: Many cloud systems use single-region storage and replication for fault tolerance, but this can still leave us vulnerable to regional failures or high latencies if users are geographically distant from the region.

New Approach:

By replicating the aggregated data to multiple regions, we achieve geographic redundancy and fault tolerance. In case one region becomes inaccessible, the other region(s) can still serve the data. This distributes the data load and ensures that data can be accessed even in case of failures in one region, improving system resilience.
Impact:

This improves availability and redundancy in a cloud system, addressing the typical problem of relying on a single region. If one region faces failure or heavy load, others can still serve the data.

4. Customizable Replication Strategies
Problem: The standard cloud model doesnt always offer customizable ways to control data replication, especially when dealing with real-time data from IoT or edge devices.

Traditional Solutions: Often, cloud providers replicate all data across regions, but this may not be efficient when only small parts of the data need to be replicated.

New Approach:

We can implement custom replication strategies based on what data is actually needed in different regions. For instance, by replicating only the aggregated data, we avoid transferring unnecessary raw sensor readings.
we\ could easily tweak the replication model to suit specific needs (e.g., real-time vs batch replication, frequency of updates, and region-specific data requirements).
Impact:

By giving more control over how and when data is replicated, we can optimize cloud usage even further, avoiding unnecessary costs and ensuring that only relevant data is available across regions.
'''