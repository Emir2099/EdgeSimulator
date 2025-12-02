import matplotlib.pyplot as plt
import time
import json
import sys
import os
import numpy as np

# --- FIXED PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')

if multiregion_dir not in sys.path:
    sys.path.append(multiregion_dir)

from encryption_manager import EncryptionManager
from compression_manager import CompressionManager, CompressionType
from anomaly_detector import AnomalyDetector

# --- SETUP ---
encryptor = EncryptionManager()
compressor = CompressionManager(CompressionType.ZLIB)
detector = AnomalyDetector()
# Train detector briefly so it works
detector.fit([[25, 50], [26, 51], [24, 49]] * 10)

times = {'Anomaly Detection': [], 'Compression': [], 'Encryption': []}
payload = json.dumps({"temp": 25.5, "humidity": 50.2, "log": "A" * 500}).encode()
features = [25.5, 50.2]

# --- RUN LOOPS ---
for _ in range(100):
    # 1. Anomaly Time
    t0 = time.perf_counter()
    detector.predict(features)
    times['Anomaly Detection'].append((time.perf_counter() - t0) * 1000) # to ms

    # 2. Compression Time
    t0 = time.perf_counter()
    compressed = compressor.compress(payload)
    times['Compression'].append((time.perf_counter() - t0) * 1000)

    # 3. Encryption Time
    t0 = time.perf_counter()
    encryptor.encrypt(compressed)
    times['Encryption'].append((time.perf_counter() - t0) * 1000)

# --- PLOTTING ---
categories = list(times.keys())
averages = [np.mean(times[c]) for c in categories]
std_dev = [np.std(times[c]) for c in categories]

plt.figure(figsize=(10, 6))
bars = plt.bar(categories, averages, yerr=std_dev, capsize=5, 
               color=['#FFCC80', '#9FA8DA', '#E6EE9C'], edgecolor='black')

plt.title("System Latency Breakdown (Overhead Analysis)", fontsize=14)
plt.ylabel("Processing Time (milliseconds)")
plt.xlabel("Pipeline Stage")

# Add text labels
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 0.01, f'{yval:.3f} ms', ha='center', va='bottom')

plt.grid(axis='y', alpha=0.3)
plt.savefig('latency_breakdown.png', dpi=300)
print("Graph generated: latency_breakdown.png")