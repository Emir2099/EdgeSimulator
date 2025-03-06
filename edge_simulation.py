import pandas as pd
import random
import time
import json
import os
import threading
from datetime import datetime
# Simulate sensor data generation
def generate_sensor_data():
    return {
        "timestamp": pd.Timestamp.now(),
        "temperature": round(random.uniform(20, 30), 2),
        "humidity": round(random.uniform(40, 60), 2)
    }

# Aggregate data at the edge
def aggregate_data(data):
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    hourly_summary = df.resample('H').mean()
    return hourly_summary.reset_index().to_dict(orient='records')

# Simulate edge device
def edge_device():
    cloud_directory = "cloud_storage"
    os.makedirs(cloud_directory, exist_ok=True)  # Ensure cloud directory exists

    sensor_data = []
    while True:
        # Generate new data every minute
        sensor_data.append(generate_sensor_data())
        print(f"New sensor data: {sensor_data[-1]}")
        
        # Simulate hourly aggregation
        if len(sensor_data) >= 10:  # Simulate 10-minute intervals instead of 1 hour for testing
            summary = aggregate_data(sensor_data)
            print("Aggregated Data:", summary)
            save_to_cloud(summary)
            sensor_data.clear()
        time.sleep(1)  # Simulate 1-minute intervals (use 1 second for faster testing)

# Save aggregated data to a simulated cloud
def save_to_cloud(data):
    cloud_directory = "cloud_storage"
    os.makedirs(cloud_directory, exist_ok=True)
    file_name = os.path.join(cloud_directory, f"aggregated_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")

    # Convert Timestamps to strings
    for record in data:
        if isinstance(record['timestamp'], pd.Timestamp):
            record['timestamp'] = record['timestamp'].isoformat()

    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)

# Simulate inter-region replication by copying files to another directory
def replicate_data():
    cloud_directory = "cloud_storage"
    replicated_directory = "replicated_storage"
    
    # Ensure both directories exist
    os.makedirs(cloud_directory, exist_ok=True)
    os.makedirs(replicated_directory, exist_ok=True)

    for file_name in os.listdir(cloud_directory):
        src_path = os.path.join(cloud_directory, file_name)
        dest_path = os.path.join(replicated_directory, file_name)

        if not os.path.exists(dest_path):  # Avoid redundant copies
            with open(src_path, "r") as src, open(dest_path, "w") as dest:
                dest.write(src.read())
            print(f"Replicated {file_name} to replicated storage")

# Simulate cloud-side processing of aggregated data
def cloud_processing():
    cloud_directory = "cloud_storage"
    replicated_directory = "replicated_storage"
    os.makedirs(replicated_directory, exist_ok=True)

    for file_name in os.listdir(cloud_directory):
        file_path = os.path.join(cloud_directory, file_name)
        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            # Process data (example replication)
            replicated_file_path = os.path.join(replicated_directory, file_name)
            with open(replicated_file_path, "w") as rf:
                json.dump(data, rf, indent=4)

            print(f"Replicated {file_name} to replicated storage")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Skipping invalid file {file_name}: {e}")


# Run the simulation
if __name__ == "__main__":
    # Start the edge device in a separate thread
    edge_thread = threading.Thread(target=edge_device, daemon=True)
    edge_thread.start()

    # Periodically replicate and process data
    while True:
        print("\n--- Simulating Replication and Processing ---")
        replicate_data()
        cloud_processing()
        time.sleep(5)  # Run replication and processing every 5 seconds
