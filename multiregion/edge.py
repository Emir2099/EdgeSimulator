import os
import json
import random
import threading
import time
import pandas as pd
from datetime import datetime
from load_balancer import LoadBalancer
from compression_manager import CompressionManager, CompressionType
from anomaly_detector import AnomalyDetector
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

# Load balancer — alpha=0.7, load_threshold=1000 bytes (operationalises 80% policy)
load_balancer = LoadBalancer(regions, alpha=0.7, load_threshold=1000)

# Compression manager — tau=0.5 efficiency threshold
compression_manager = CompressionManager(CompressionType.ZLIB, tau=0.5)

# Anomaly detector — contamination=0.1, delta=0.5, random_state=42
anomaly_detector = AnomalyDetector(contamination=0.1, delta=0.5, random_state=42)

# Smart cache
smart_cache = SmartCache(max_size=20, ttl=300)

# Encryption manager (AES-256-GCM)
encryption_manager = EncryptionManager()

# Version control (SQLite-backed)
version_control = DataVersionControl(os.path.dirname(os.path.abspath(__file__)))

# Health monitor
health_monitor = HealthMonitor(check_interval=5)
health_monitor.update_threshold('disk_percent', 85.0)
health_monitor.update_threshold('cpu_percent', 75.0)


# ------------------------------------------------------------------
# PARAMETER-DRIVEN SIMULATION: 4G/LTE Edge Network Latency Model
# Base latency ~ N(mu=50ms, sigma=15ms), floored at 10ms.
# Transmission delay modelled from 4G average upload (10 Mbps).
# Source: documented 4G/LTE backhaul characteristics.
# ------------------------------------------------------------------
def simulate_network_latency(data_size_bytes=0, connection_type="4G"):
    """
    Simulate network transmission time using empirically documented
    4G/LTE parameters rather than hardcoded constants.
    """
    # Base latency (ping) ~ N(50ms, 15ms)
    base_latency = max(0.010, random.gauss(0.050, 0.015))

    # Transmission delay based on connection type
    # 4G average upload: 10 Mbps (1.25 MB/s)
    # WAN inter-region: 100 Mbps (12.5 MB/s)
    bandwidth_bps = 1.25 * 1024 * 1024 if connection_type == "4G" \
                    else 12.5 * 1024 * 1024

    transmission_delay = (data_size_bytes / bandwidth_bps) \
                         if data_size_bytes > 0 else 0

    total_delay = base_latency + transmission_delay
    time.sleep(total_delay)
    return total_delay


def determine_priority(summary, anomaly_prediction):
    """
    Map anomaly detection output to priority label.
    Implements Eq. (7): c* = LZMA if anomaly, else arg min J(c).
    """
    if anomaly_prediction == -1:
        return "high"
    elif summary['temperature'] > 20 or summary['humidity'] < 30:
        return "medium"
    else:
        return "low"


def generate_sensor_data():
    """
    Generate synthetic IoT sensor data from documented distributions
    (Section 6.1):
        temperature ~ U(20.0, 30.0) degrees C  (normal range)
        humidity    ~ U(40.0, 60.0) percent     (normal range)
    Large log pattern included to test compression efficiency (RQ2).
    """
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
        data_buffer.append(new_data)

        if len(data_buffer) >= aggregation_interval:
            summary = {
                'timestamp': pd.Timestamp.now().floor('min'),
                'temperature': sum(d['temperature'] for d in data_buffer) / len(data_buffer),
                'humidity':    sum(d['humidity']    for d in data_buffer) / len(data_buffer),
            }

            features = [summary['temperature'], summary['humidity']]
            prediction = anomaly_detector.predict(features)
            anomaly_detector.update(features)

            priority = determine_priority(summary, prediction)
            summary["priority"] = priority

            if priority == "high":
                print(f"[{region}] WARNING: High priority / Anomaly detected!")

            save_to_cloud(region, summary)
            data_buffer.clear()

        time.sleep(1)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)


def save_to_cloud(region, data):
    """
    Core pipeline: compression -> encryption -> routing -> storage.

    Implements the closed-loop feedback between anomaly detection and
    compression path selection (Eq. 7), and between compression output
    size and load metric update (Section 2.4 novel contribution).
    """
    # Serialise data
    json_data = json.dumps(data, cls=DateTimeEncoder).encode('utf-8')

    # ------------------------------------------------------------------
    # Adaptive Compression (Algorithm 1) — now fully in CompressionManager
    # priority='high' -> LZMA (Eq. 7 override)
    # priority='normal' -> ZLIB with BZ2 fallback if eta < tau=0.5
    # ------------------------------------------------------------------
    priority = 'high' if data.get("priority") == "high" else 'normal'
    compressed_data, algorithm_used, eta = compression_manager.adaptive_compress(
        json_data, priority=priority
    )

    # AES-256-GCM encryption 
    encrypted_data = encryption_manager.encrypt(compressed_data)
    if encrypted_data is None:
        return

    data_size = len(encrypted_data)

    # ------------------------------------------------------------------
    # Load Balancing — routing decision via LoadBalancer.get_target_region()
    # Implements Algorithm 2: arg min selection + hysteresis check (Eq. 3)
    # L_i(t) is updated POST-compression (closed feedback loop, Section 2.4)
    # ------------------------------------------------------------------
    target_region = load_balancer.get_target_region(region)

    if target_region != region:
        print(f"Load redirect: {region} -> {target_region} "
              f"(load {load_balancer.region_loads[region]} > threshold, "
              f"hysteresis check passed)")
        simulate_network_latency(data_size, "WAN")

    file_name = f"aggregated_data_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.json.gz"
    file_path = os.path.join(cloud_directories[target_region], file_name)

    # Simulate upload latency (RQ4)
    upload_latency = simulate_network_latency(data_size, "4G")

    with open(file_path, 'wb') as f:
        f.write(encrypted_data)

    # Version control — SQLite atomic write (RQ3)
    metadata = {
        'region': target_region,
        'priority': data.get('priority', 'low'),
        'algorithm': algorithm_used.value,
        'compression_ratio': eta,
        'upload_latency_ms': upload_latency * 1000
    }
    version_control.save_version(file_path, data, metadata)

    print(f"[{target_region}] Saved. Algo={algorithm_used.value} "
          f"eta={eta:.2f} | Latency={upload_latency*1000:.1f}ms "
          f"| Loads={load_balancer.region_loads}")

    # Update L_i(t) AFTER compression (closed feedback loop)
    load_balancer.update_load(target_region, data_size)
    smart_cache.set(file_path, data)


def replicate_data(source_region, target_region):
    source_dir = cloud_directories[source_region]
    target_dir = replicated_directories[target_region]

    while True:
        try:
            files = sorted(
                os.listdir(source_dir),
                key=lambda x: os.path.getmtime(os.path.join(source_dir, x))
            )
            for file_name in files:
                source_file = os.path.join(source_dir, file_name)
                target_file = os.path.join(target_dir, file_name)

                if not os.path.exists(target_file):
                    file_size = os.path.getsize(source_file)
                    latency = simulate_network_latency(file_size, "WAN")
                    data = read_compressed_data(source_file)
                    if data:
                        with open(target_file, 'w') as tgt:
                            json.dump(data, tgt, cls=DateTimeEncoder)
                        print(f"Replicated {file_name} to {target_region} "
                              f"({latency*1000:.1f}ms delay)")
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
    except Exception:
        pass
    return None


def main():
    try:
        health_monitor.start()
        print("--- S-Edge Framework Started (Parameter-Driven Simulation Mode) ---")
        print("Initializing SQLite Storage Engine...")
        print("Initializing 4G/LTE Network Simulation (mu=50ms, sigma=15ms)...")
        print(f"Load Balancer: alpha={load_balancer.alpha}, "
              f"L_thresh={load_balancer.load_threshold} bytes")
        print(f"Compression Manager: tau={compression_manager.tau}")
        print(f"Anomaly Detector: contamination={anomaly_detector.contamination}, "
              f"delta={anomaly_detector.delta}")

        dashboard = MonitoringDashboard(health_monitor, load_balancer, compression_manager)
        dashboard_process = dashboard.start()

        edge_threads = []
        for region in regions:
            thread = threading.Thread(
                target=edge_device, args=(region,), daemon=True
            )
            thread.start()
            edge_threads.append(thread)

        replication_threads = []
        for i, source_region in enumerate(regions):
            target_region = regions[(i + 1) % len(regions)]
            thread = threading.Thread(
                target=replicate_data,
                args=(source_region, target_region),
                daemon=True
            )
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
