import matplotlib.pyplot as plt
import random
import json
import numpy as np
import sys
import os

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')

if multiregion_dir not in sys.path:
    sys.path.append(multiregion_dir)

from compression_manager import CompressionManager, CompressionType

# --- CONFIGURATION ---
NUM_SAMPLES = 10        # Fewer samples because files are large (5MB takes time)
ANOMALY_RATE = 0.4      # 40% of data is "High Priority"

def generate_payload(is_anomaly):
    """
    Generates LARGE payloads (approx 5 MB) with realistic repetition.
    This allows LZMA to show its superiority over ZLIB.
    """
    if is_anomaly:
        # ANOMALY: Highly repetitive "System Crash Log"
        # LZMA excels at finding patterns over long distances
        chunk = "CRITICAL_KERNEL_FAILURE_SEGMENT_FAULT_AT_0x84732 "
        # Repeat to reach ~5MB
        # Length 45 * 120,000 ~= 5.4 MB
        large_log = chunk * 120000 
        payload = {"type": "CRITICAL_DUMP", "data": large_log}
    else:
        # NORMAL: Structured IoT Sensor Data Batch
        # ZLIB handles this fine, but LZMA is still slightly better (but slower)
        # We simulate a CSV-style export
        # "id,temp,humidity,status\n" repeated
        rows = ["101,23.4,45,OK\n", "102,23.5,46,OK\n", "103,24.1,44,OK\n"]
        # Repeat to reach ~2MB
        large_csv = "".join(rows * 40000)
        payload = {"type": "BATCH_UPLOAD", "data": large_csv}
        
    return json.dumps(payload).encode()

# --- RUN EXPERIMENT ---
sizes_zlib = []
sizes_lzma = []
sizes_adaptive = []

mgr = CompressionManager()

print("Running Compression Benchmark with ~5MB Payloads...")
print("This may take 10-20 seconds per sample. Please wait.")

for i in range(NUM_SAMPLES):
    is_anomaly = random.random() < ANOMALY_RATE
    data = generate_payload(is_anomaly)
    
    # 1. Static ZLIB
    mgr.compression_type = CompressionType.ZLIB
    z_size = len(mgr.compress(data))
    sizes_zlib.append(z_size)
    
    # 2. Static LZMA
    mgr.compression_type = CompressionType.LZMA
    l_size = len(mgr.compress(data))
    sizes_lzma.append(l_size)
    
    # 3. S-Edge Adaptive (Your Logic)
    if is_anomaly:
        # High Priority -> LZMA (Best compression)
        mgr.compression_type = CompressionType.LZMA
        sizes_adaptive.append(l_size)
    else:
        # Normal Priority -> ZLIB (Good enough, fast)
        mgr.compression_type = CompressionType.ZLIB
        sizes_adaptive.append(z_size)
    
    print(f"Sample {i+1}/{NUM_SAMPLES} processed.")

# --- PLOTTING ---
labels = ['Static ZLIB', 'Static LZMA', 'S-Edge Adaptive']
means = [np.mean(sizes_zlib), np.mean(sizes_lzma), np.mean(sizes_adaptive)]

plt.figure(figsize=(9, 6))
# Colors: Blue (Baseline), Green (Best possible), Orange (Yours - Balanced)
bars = plt.bar(labels, means, color=['#90CAF9', '#A5D6A7', '#FFCC80'], edgecolor='black')

# Add values on top (Converted to KB/MB for readability)
for bar in bars:
    yval = bar.get_height()
    # Convert to MB or KB depending on size
    val_str = f"{yval/1024:.0f} KB" if yval < 1024*1024 else f"{yval/(1024*1024):.2f} MB"
    plt.text(bar.get_x() + bar.get_width()/2, yval + (yval*0.02), val_str, ha='center', va='bottom', fontweight='bold')

plt.title("Storage Efficiency: Large Log Analysis (~5MB)", fontsize=14)
plt.ylabel("Average Compressed Size - Lower is Better")
plt.grid(axis='y', alpha=0.3)

plt.savefig('compression_comparison.png', dpi=300)
print("Graph generated: compression_comparison.png")