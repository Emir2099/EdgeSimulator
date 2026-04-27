import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import random
import json
import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')
if multiregion_dir not in sys.path:
    sys.path.append(multiregion_dir)

from compression_manager import CompressionManager, CompressionType

# Must match compression_benchmark.py exactly
NUM_SAMPLES  = 10
ANOMALY_RATE = 0.10   # 10% — matches contamination=0.1
SYSTEM_LOG   = "SYSTEM_STATUS_OK_CHECK_SENSOR_VOLTAGE_STABLE_ " * 5000

def generate_payload(seed):
    """
    Generates ~5.5MB mixed batch payload matching compression_benchmark.py
    and the actual edge.py pipeline (summary + raw_readings for anomalies).
    """
    rng = random.Random(seed)
    records = []
    for _ in range(25):   # 25 records * ~220KB each = ~5.5MB
        is_anomaly = rng.random() < ANOMALY_RATE
        records.append({
            'timestamp':   '2024-01-15T10:30:00Z',
            'temperature': round(
                rng.uniform(33.0, 40.0) if is_anomaly
                else rng.uniform(20.0, 30.0), 2),
            'humidity': round(
                rng.uniform(15.0, 25.0) if is_anomaly
                else rng.uniform(40.0, 60.0), 2),
            'system_log': SYSTEM_LOG,
            'priority':   'high' if is_anomaly else 'low'
        })
    return json.dumps(records).encode('utf-8'), \
           [r for r in records if r['priority'] == 'high'], \
           [r for r in records if r['priority'] == 'low']

import zlib, lzma, bz2

sizes_zlib     = []
sizes_lzma     = []
sizes_adaptive = []

mgr = CompressionManager()
print("Running Compression Benchmark (~5.5MB payloads, 10 runs)...")

for i in range(NUM_SAMPLES):
    seed = 42 + i
    data, anomaly_records, normal_records = generate_payload(seed)

    # 1. Static ZLIB — all traffic
    mgr.compression_type = CompressionType.ZLIB
    z_size = len(mgr.compress(data))
    sizes_zlib.append(z_size)

    # 2. Static LZMA — all traffic
    mgr.compression_type = CompressionType.LZMA
    l_size = len(mgr.compress(data))
    sizes_lzma.append(l_size)

    # 3. S-Edge Adaptive — LZMA for anomaly, ZLIB for normal (Algorithm 1)
    normal_bytes  = json.dumps(normal_records).encode('utf-8')  if normal_records  else b''
    anomaly_bytes = json.dumps(anomaly_records).encode('utf-8') if anomaly_records else b''

    mgr.compression_type = CompressionType.ZLIB
    normal_out  = mgr.compress(normal_bytes)  if normal_bytes  else b''
    mgr.compression_type = CompressionType.LZMA
    anomaly_out = mgr.compress(anomaly_bytes) if anomaly_bytes else b''
    adaptive_size = len(normal_out) + len(anomaly_out)
    sizes_adaptive.append(adaptive_size)

    print(f"  Run {i+1}/{NUM_SAMPLES}: "
          f"ZLIB={z_size/1024:.1f}KB  "
          f"LZMA={l_size/1024:.1f}KB  "
          f"S-Edge={adaptive_size/1024:.1f}KB")

# --- PLOTTING ---
labels = ['Static ZLIB', 'Static LZMA', 'S-Edge Adaptive']
means  = [np.mean(sizes_zlib)/1024,
          np.mean(sizes_lzma)/1024,
          np.mean(sizes_adaptive)/1024]
stds   = [np.std(sizes_zlib)/1024,
          np.std(sizes_lzma)/1024,
          np.std(sizes_adaptive)/1024]

print(f"\nMeans: ZLIB={means[0]:.2f}KB  "
      f"LZMA={means[1]:.2f}KB  S-Edge={means[2]:.2f}KB")

plt.figure(figsize=(9, 6))
bars = plt.bar(labels, means,
               color=['#90CAF9', '#A5D6A7', '#FFCC80'],
               edgecolor='black',
               yerr=stds, capsize=5)

for bar, mean, std in zip(bars, means, stds):
    plt.text(bar.get_x() + bar.get_width()/2,
             mean + std + mean*0.02,
             f"{mean:.1f} KB",
             ha='center', va='bottom', fontweight='bold')

plt.title("Storage Efficiency: Large Log Analysis (~5.5MB)", fontsize=14)
plt.ylabel("Average Compressed Size (KB) — Lower is Better")
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('compression_comparison.png', dpi=300)
print("Graph saved: compression_comparison.png")