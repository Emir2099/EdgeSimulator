import matplotlib.pyplot as plt
import time
import json
import sys
import os
import shutil
import random
import numpy as np

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')

if multiregion_dir not in sys.path:
    sys.path.append(multiregion_dir)

from version_control import DataVersionControl

# --- SETUP ---
TEST_DIR = os.path.join(current_dir, "recovery_test_data")
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)
os.makedirs(TEST_DIR, exist_ok=True)

# Initialize your Version Control System
vc = DataVersionControl(TEST_DIR)
test_file = os.path.join(TEST_DIR, "sensor_log.json")

# Create initial stable version
initial_data = {"status": "stable", "readings": [1, 2, 3]}
with open(test_file, 'w') as f:
    json.dump(initial_data, f)
vc.save_version(test_file, initial_data, metadata={"state": "stable"})

# --- RUN EXPERIMENT ---
NUM_TRIALS = 50
recovery_times = []

print(f"Simulating {NUM_TRIALS} Failure & Recovery Events...")

for i in range(NUM_TRIALS):
    # 1. Simulate Corruption (Overwrite file with garbage)
    with open(test_file, 'w') as f:
        f.write("CORRUPTED_DATA_SEGMENT_FAULT_" * 100)
    
    # 2. Measure Recovery Time
    start_time = time.perf_counter()
    
    # Trigger your actual rollback logic
    success = vc.rollback(test_file, version_index=-1)
    
    end_time = time.perf_counter()
    
    if success:
        # Convert to milliseconds for better graph readability
        recovery_times.append((end_time - start_time) * 1000)
    else:
        print(f"Failed to recover on trial {i}")

# --- PLOTTING ---
plt.figure(figsize=(10, 6))

# Plot the raw data points
plt.plot(recovery_times, label='Recovery Latency per Event', color='#EF5350', marker='o', markersize=4, linestyle='-', alpha=0.7)

# Calculate stats
avg_time = np.mean(recovery_times)
max_time = np.max(recovery_times)

# Add "1.0 Second Threshold" line (1000 ms)
plt.axhline(y=1000, color='black', linestyle='--', linewidth=2, label='Critical Threshold (1.0s)')

# Add Average Line
plt.axhline(y=avg_time, color='blue', linestyle='-.', linewidth=2, label=f'Average: {avg_time:.2f} ms')

plt.title("Fault Tolerance: Rollback Recovery Latency Analysis", fontsize=14)
plt.xlabel("Simulated Failure Events (Trial #)")
plt.ylabel("Recovery Time (milliseconds)")
plt.legend(loc='upper right')
plt.grid(True, alpha=0.3)

# Add text annotation
plt.text(NUM_TRIALS/2, avg_time + 5, f"Mean Recovery: {avg_time:.2f} ms", ha='center', color='blue', fontweight='bold')

plt.tight_layout()
plt.savefig('recovery_latency.png', dpi=300)
print(f"Graph generated: recovery_latency.png (Avg: {avg_time:.4f} ms)")

# Cleanup
try:
    shutil.rmtree(TEST_DIR)
except:
    pass