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
from compression_manager import CompressionManager, CompressionType
from anomaly_detector import AnomalyDetector
from smart_cache import SmartCache
from encryption_manager import EncryptionManager
from version_control import DataVersionControl
from health_monitor import HealthMonitor
import psutil

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

# Compression manager
compression_manager = CompressionManager(CompressionType.ZLIB)

# Anomaly detector
anomaly_detector = AnomalyDetector(contamination=0.1)

# Smart cache 
smart_cache = SmartCache(max_size=20, ttl=300)

# Encryption manager
encryption_manager = EncryptionManager()

# Version control
version_control = DataVersionControl(os.path.dirname(os.path.abspath(__file__)))

# Health monitor
health_monitor = HealthMonitor(check_interval=5)
health_monitor.update_threshold('disk_percent', 85.0)  # More reasonable disk threshold
health_monitor.update_threshold('cpu_percent', 75.0)   # More reasonable CPU threshold

def determine_priority(summary, anomaly_prediction):
    """
    Determines the priority level based on the anomaly detection and sensor thresholds.
    If an anomaly is detected, mark as 'high'. Otherwise, if the aggregated values
    are extreme (e.g., temperature > 70 or humidity < 30), mark as 'medium'.
    Else return 'low'.
    """
    if anomaly_prediction == -1:
        return "high"
    elif summary['temperature'] > 20 or summary['humidity'] < 30:
        return "medium"
    else:
        return "low"


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
            
            # Run anomaly detection on aggregated data
            features = [summary['temperature'], summary['humidity']]
            prediction = anomaly_detector.predict(features)
            if prediction == -1:
                print(f"[{region}] Anomaly detected in aggregated data: {summary}")
            # Update anomaly detector with the new data point
            anomaly_detector.update(features)

            # Determine priority based on anomaly detection and thresholds
            priority = determine_priority(summary, prediction)
            summary["priority"] = priority
            if priority == "high":
                print(f"[{region}] High priority data detected.")

            # Save aggregated data if no anomaly is detected (or even if detected, depending on requirements)
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
    # If high priority, mark filename and change compression algorithm
    file_flag = ""
    # Save current compression type to revert later
    original_comp_type = compression_manager.compression_type
    if data.get("priority") == "high":
        file_flag = "PRIORITY_"
        # For high priority, use best compression (e.g., LZMA) to preserve data fidelity
        compression_manager.compression_type = CompressionType.LZMA
    else:
        # For normal data, use default ZLIB compression
        compression_manager.compression_type = CompressionType.ZLIB
    file_name = f"aggregated_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.json.gz"
    
    # Compress and encrypt data
    json_data = json.dumps(data, cls=DateTimeEncoder).encode('utf-8')
    compressed_data = compression_manager.compress(json_data)
    encrypted_data = encryption_manager.encrypt(compressed_data)
    
    if encrypted_data is None:
        print(f"Failed to encrypt data for {region}")
        return
    
    data_size = len(encrypted_data)
    
    # Calculate compression ratio and update stats
    compression_ratio = compression_manager.update_stats(len(json_data), data_size)
    
    # Get optimal region before updating load
    current_load = load_balancer.region_loads[region]
    optimal_region = load_balancer.get_optimal_region()
    
    if optimal_region != region and load_balancer.region_loads[optimal_region] < current_load * 0.7:
        print(f"Redirecting data from {region} to {optimal_region} for better load distribution")
        region = optimal_region
    
    file_path = os.path.join(cloud_directories[region], file_name)
    
    # Save encrypted data
    with open(file_path, 'wb') as f:
        f.write(encrypted_data)
    
    # Add version control
    metadata = {
        'region': region,
        'priority': data.get('priority', 'low'),
        'compression_ratio': compression_ratio,
        'encryption_status': 'encrypted'
    }
    version = version_control.save_version(file_path, data, metadata)
    print(f"Saved version {version['timestamp']} with checksum {version['checksum']}")
    
    print(f"Compression ratio: {compression_ratio:.2f}%")
    print(f"Average compression ratio: {compression_manager.get_average_ratio():.2f}%")
    print(f"Current loads: {load_balancer.region_loads}")
    
    # Update load balancer
    load_balancer.update_load(region, data_size)
    
    # Optionally, cache the new aggregated data so that future reads are fast
    smart_cache.set(file_path, data)
    
    # Revert compression manager's type back to original if changed
    compression_manager.compression_type = original_comp_type

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
                    # Use the smart cache to get file data
                    data = read_compressed_data(source_file)
                    if data:
                        # Use the custom encoder to convert Timestamps to strings
                        with open(target_file, 'w') as tgt:
                            json.dump(data, tgt, cls=DateTimeEncoder)
                except Exception as e:
                    print(f"Error replicating file {file_name}: {str(e)}")
        time.sleep(5)



# Read compressed data from file
def read_compressed_data(file_path):
    # First, check the smart cache
    cached_data = smart_cache.get(file_path)
    if cached_data is not None:
        print(f"Serving {file_path} from cache")
        return cached_data

    # If not cached, read from disk and decompress
    try:
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
            # First decrypt
            decrypted_data = encryption_manager.decrypt(encrypted_data)
            if decrypted_data is None:
                raise Exception("Failed to decrypt data")
            
            # Then decompress
            json_data = compression_manager.decompress(decrypted_data)
            if json_data:
                data = json.loads(json_data.decode('utf-8'))
                # Cache the data for future use
                smart_cache.set(file_path, data)
                return data
    except Exception as e:
        print(f"Error reading compressed file {file_path}: {str(e)}")
    return None

# Add new function for version management
def manage_versions(file_path):
    """Utility function to manage versions of a file"""
    history = version_control.get_version_history(file_path)
    if not history:
        print(f"No version history found for {file_path}")
        return
    
    print(f"\nVersion history for {file_path}:")
    for i, version in enumerate(history):
        print(f"Version {i}:")
        print(f"  Timestamp: {version['timestamp']}")
        print(f"  Checksum: {version['checksum']}")
        print(f"  Metadata: {version['metadata']}")
    
    return history

# Start the simulation
def main():
    try:
        # Start health monitoring
        health_monitor.start()
        print("Health monitoring system started")
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Initialize log file with current date
        log_file = os.path.join(logs_dir, f'health_report_{datetime.now().strftime("%Y%m%d")}.log')
        
        # Start threads
        edge_threads = []
        for region in regions:
            thread = threading.Thread(target=edge_device, args=(region,), daemon=True)
            thread.start()
            edge_threads.append(thread)

        # Start inter-region replication threads
        replication_threads = []
        for i, source_region in enumerate(regions):
            target_region = regions[(i + 1) % len(regions)]
            thread = threading.Thread(target=replicate_data, 
                                   args=(source_region, target_region),
                                   daemon=True)
            thread.start()
            replication_threads.append(thread)

        # Monitor and report system health
        while True:
            time.sleep(30)  # Report every 30 seconds
            metrics = health_monitor.get_metrics_summary()
            
            # Format the report
            report = []
            report.append(f"\n{'='*80}")
            report.append(f"System Health Report @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"{'='*80}\n")
            
            report.append("System Metrics:")
            report.append("-" * 50)
            for metric, values in metrics.items():
                if metric != 'timestamp':
                    report.append(
                        f"{metric:<18}: {values['current']:>6.2f} | "
                        f"Avg={values['avg']:>6.2f} | "
                        f"Max={values['max']:>6.2f} | "
                        f"Min={values['min']:>6.2f}")
            
            # Add alerts if any
            recent_alerts = health_monitor.get_recent_alerts()
            if recent_alerts:
                report.append("\nRecent Alerts:")
                report.append("-" * 50)
                for alert in recent_alerts:
                    report.append(
                        f"[{alert['timestamp']}] {alert['metric']}: "
                        f"{alert['value']:.2f} > {alert['threshold']:.2f}")
            
            # Write to log file
            with open(log_file, 'a') as f:
                f.write('\n'.join(report) + '\n')
            
            # Show minimal console output
            print(f"\rHealth report updated @ {datetime.now().strftime('%H:%M:%S')} | "
                  f"CPU: {metrics['cpu_percent']['current']:.1f}% | "
                  f"MEM: {metrics['memory_percent']['current']:.1f}%", end='')

    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        health_monitor.stop()
        
        print("Waiting for threads to complete...")
        for thread in edge_threads + replication_threads:
            thread.join(timeout=2.0)
            
        print("Shutdown complete")
        
    except Exception as e:
        print(f"\nError in main loop: {str(e)}")
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