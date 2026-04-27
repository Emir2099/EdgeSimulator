import os
import json
import random
import threading
import time
import pandas as pd
from datetime import datetime
from multiregion.deprecated.load_balancer import LoadBalancer
import zlib
from multiregion.deprecated.compression_manager import CompressionManager, CompressionType
from multiregion.deprecated.anomaly_detector import AnomalyDetector
from smart_cache import SmartCache
from encryption_manager import EncryptionManager
from version_control import DataVersionControl
from health_monitor import HealthMonitor
import psutil
from monitoring_dashboard import MonitoringDashboard

# Directories for regions
regions = ['region_1', 'region_2', 'region_3']
replicated_directories = {region: f"{region}_replicated_storage" for region in regions}
cloud_directories = {region: f"{region}_cloud_storage" for region in regions}

# Ensure directories exist
for directory in cloud_directories.values():
    os.makedirs(directory, exist_ok=True)
for directory in replicated_directories.values():
    os.makedirs(directory, exist_ok=True)

# Load balancer (Now uses RLock and Latency Injection)
load_balancer = LoadBalancer(regions)

# Compression manager
compression_manager = CompressionManager(CompressionType.ZLIB)

# Anomaly detector
anomaly_detector = AnomalyDetector(contamination=0.1)

# Smart cache 
smart_cache = SmartCache(max_size=20, ttl=300)

# Encryption manager
encryption_manager = EncryptionManager()

# Version control (Now uses SQLite)
version_control = DataVersionControl(os.path.dirname(os.path.abspath(__file__)))

# Health monitor
health_monitor = HealthMonitor(check_interval=5)
health_monitor.update_threshold('disk_percent', 85.0)
health_monitor.update_threshold('cpu_percent', 75.0)

# --- TRACE-DRIVEN SIMULATION HELPER ---
def simulate_network_latency(data_size_bytes=0, connection_type="4G"):
    """
    Injected methodology for RQ1/RQ4.
    Simulates network transmission time based on Gaussian distribution + data size.
    """
    # 1. Base Latency (Ping) - Gaussian (Mean=50ms, StdDev=15ms)
    base_latency = max(0.010, random.gauss(0.050, 0.015))
    
    # 2. Transmission Delay (Bandwidth)
    # 4G Avg Upload: 10 Mbps (approx 1.25 MB/s)
    # WAN (Inter-region): 100 Mbps
    bandwidth_speed = 1.25 * 1024 * 1024 if connection_type == "4G" else 12.5 * 1024 * 1024
    
    transmission_delay = 0
    if data_size_bytes > 0:
        transmission_delay = data_size_bytes / bandwidth_speed
    
    total_delay = base_latency + transmission_delay
    time.sleep(total_delay) # The actual "Wait"
    return total_delay

def determine_priority(summary, anomaly_prediction):
    if anomaly_prediction == -1:
        return "high"
    elif summary['temperature'] > 20 or summary['humidity'] < 30:
        return "medium"
    else:
        return "low"

def generate_sensor_data():
    # Massive log pattern to test compression efficiency (RQ2)
    log_pattern = "SYSTEM_STATUS_OK_CHECK_SENSOR_VOLTAGE_STABLE_ " * 5000
    
    return {
        'timestamp': pd.Timestamp.now(),
        'temperature': round(random.uniform(20.0, 30.0), 2),
        'humidity': round(random.uniform(40.0, 60.0), 2),
        'system_log': log_pattern 
    }

def edge_device(region):
    data_buffer = []
    aggregation_interval = 5  # seconds

    while True:
        new_data = generate_sensor_data()
        # Commented out print to reduce console spam, uncomment for debug
        # print(f"[{region}] New sensor data generated")
        data_buffer.append(new_data)

        if len(data_buffer) >= aggregation_interval:
            summary = {
                'timestamp': pd.Timestamp.now().floor('min'),
                'temperature': sum(d['temperature'] for d in data_buffer) / len(data_buffer),
                'humidity': sum(d['humidity'] for d in data_buffer) / len(data_buffer),
            }
            
            features = [summary['temperature'], summary['humidity']]
            prediction = anomaly_detector.predict(features)
            anomaly_detector.update(features)

            priority = determine_priority(summary, prediction)
            summary["priority"] = priority
            if priority == "high":
                print(f"[{region}] ⚠️ High priority/Anomaly detected!")

            save_to_cloud(region, summary)
            data_buffer.clear()

        time.sleep(1)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

def save_to_cloud(region, data):
    file_flag = ""
    original_comp_type = compression_manager.compression_type
    
    # Serialize first so json_data is available for adaptive compression
    json_data = json.dumps(data, cls=DateTimeEncoder).encode('utf-8')

    # Adaptive Compression Logic (RQ2)
    if data.get("priority") == "high":
        file_flag = "PRIORITY_"
        compression_manager.compression_type = CompressionType.LZMA
    else:
        compression_manager.compression_type = CompressionType.ZLIB
        compressed = compression_manager.compress(json_data)
        ratio = (len(json_data) - len(compressed)) / len(json_data)
        if ratio < 0.5:
            compression_manager.compression_type = CompressionType.BZ2
        
    file_name = f"aggregated_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.json.gz"
    
    # Processing Overhead (CPU)
    compressed_data = compression_manager.compress(json_data)
    encrypted_data = encryption_manager.encrypt(compressed_data)
    
    if encrypted_data is None:
        return
    
    data_size = len(encrypted_data)
    compression_ratio = compression_manager.update_stats(len(json_data), data_size)
    
    # Load Balancing Logic (RQ1)
    current_load = load_balancer.region_loads[region]
    optimal_region = load_balancer.get_optimal_region()
    
    target_region = region
    # Hysteresis check (0.7) to prevent flapping
    if optimal_region != region and load_balancer.region_loads[optimal_region] < current_load * 0.7:
        print(f"⚖️ Redirecting load from {region} to {optimal_region}")
        target_region = optimal_region
        # Simulate the cost of redirecting traffic (Latency Penalty)
        simulate_network_latency(data_size, "WAN")
    
    file_path = os.path.join(cloud_directories[target_region], file_name)
    
    # Simulate Upload Latency (Edge to Cloud) - RQ4
    upload_latency = simulate_network_latency(data_size, "4G")
    
    with open(file_path, 'wb') as f:
        f.write(encrypted_data)
    
    # Version Control (RQ3) - Now uses SQLite internally
    metadata = {
        'region': target_region,
        'priority': data.get('priority', 'low'),
        'compression_ratio': compression_ratio,
        'upload_latency_ms': upload_latency * 1000
    }
    # This call now hits the SQLite database instead of a JSON file
    version = version_control.save_version(file_path, data, metadata)
    
    # Stats Logging
    print(f"[{target_region}] Saved. Ratio: {compression_ratio:.1f}% | Latency: {upload_latency*1000:.1f}ms | Load: {load_balancer.region_loads}")
    
    load_balancer.update_load(target_region, data_size)
    smart_cache.set(file_path, data)
    compression_manager.compression_type = original_comp_type

def replicate_data(source_region, target_region):
    source_dir = cloud_directories[source_region]
    target_dir = replicated_directories[target_region]

    while True:
        try:
            # List files and sort by modification time to process newest
            files = sorted(os.listdir(source_dir), key=lambda x: os.path.getmtime(os.path.join(source_dir, x)))
            
            for file_name in files:
                source_file = os.path.join(source_dir, file_name)
                target_file = os.path.join(target_dir, file_name)

                if not os.path.exists(target_file):
                    # Simulate Inter-Region Latency (RQ1)
                    # Get file size for realistic transfer calculation
                    file_size = os.path.getsize(source_file)
                    latency = simulate_network_latency(file_size, "WAN")
                    
                    data = read_compressed_data(source_file)
                    if data:
                        with open(target_file, 'w') as tgt:
                            json.dump(data, tgt, cls=DateTimeEncoder)
                        print(f"🔄 Replicated {file_name} to {target_region} ({latency*1000:.1f}ms delay)")
        except Exception as e:
            print(f"Replication error: {e}")
            
        time.sleep(5)

def read_compressed_data(file_path):
    cached_data = smart_cache.get(file_path)
    if cached_data is not None:
        return cached_data

    try:
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
            decrypted_data = encryption_manager.decrypt(encrypted_data)
            if decrypted_data is None:
                raise Exception("Failed to decrypt")
            
            json_data = compression_manager.decompress(decrypted_data)
            if json_data:
                data = json.loads(json_data.decode('utf-8'))
                smart_cache.set(file_path, data)
                return data
    except Exception as e:
        pass # Silently fail on read errors (simulated packet loss)
    return None

def main():
    try:
        health_monitor.start()
        print("--- S-Edge Framework Started (Trace-Driven Mode) ---")
        print("Initializing SQLite Storage Engine...")
        print("Initializing 4G/WAN Network Simulation...")
        
        dashboard = MonitoringDashboard(health_monitor, load_balancer, compression_manager)
        dashboard_process = dashboard.start()
        
        edge_threads = []
        for region in regions:
            thread = threading.Thread(target=edge_device, args=(region,), daemon=True)
            thread.start()
            edge_threads.append(thread)

        replication_threads = []
        for i, source_region in enumerate(regions):
            target_region = regions[(i + 1) % len(regions)]
            thread = threading.Thread(target=replicate_data, 
                                   args=(source_region, target_region),
                                   daemon=True)
            thread.start()
            replication_threads.append(thread)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping S-Edge Framework...")
        health_monitor.stop()
        if dashboard_process:
            dashboard_process.terminate()
        print("System Halted.")
        
    except Exception as e:
        print(f"\nCritical Error: {str(e)}")
        health_monitor.stop()

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