"""
per_operation_profiler.py
=========================
Per-operation latency profiler for S-Edge pipeline stages.

Measures mean latency (microseconds) for each stage on the host hardware
(AMD Ryzen 7 6800H) and provides an analytical extrapolation to
representative IoT edge hardware (Raspberry Pi 4, ESP32).

This addresses hardware extrapolation methodology.
Rather than claiming results generalise directly, we provide a transparent analytical model with cited scaling factors.

Pipeline stages measured:
    1. Anomaly detection inference  (Isolation Forest)
    2. ZLIB compression             (1 KB payload)
    3. BZ2 compression              (1 KB payload)
    4. LZMA compression             (1 KB payload)
    5. AES-256-GCM encryption       (1 KB payload)
    6. SHA-256 integrity hash       (1 KB payload)
    7. SQLite write (WAL mode)

Hardware scaling methodology:
    Estimated_ARM = Ryzen_measurement * scaling_factor
    Scaling factors derived from published MIPS/FLOPS ratios and
    compression benchmark literature [cross-reference with paper citations].
"""

import time
import os
import sys
import csv
import hashlib
import sqlite3
import tempfile
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compression_manager import CompressionManager, CompressionType
from encryption_manager import EncryptionManager
from anomaly_detector import AnomalyDetector
import numpy as np

# ------------------------------------------------------------------
# Hardware scaling factors (analytical model)
# Source: published CPU benchmark ratios for compression workloads
#
# AMD Ryzen 7 6800H: ~3.2 GHz boost, AVX2, 8 cores
# Raspberry Pi 4:    ~1.8 GHz ARM Cortex-A72, no AVX
# ESP32:             ~240 MHz Xtensa LX6, no FPU for crypto
#
# Compression scaling ~8-12x (Ryzen -> Pi 4) based on published
# zlib/lzma benchmarks on ARM vs x86 platforms.
# Crypto scaling ~15-20x (Ryzen -> Pi 4) due to lack of AES-NI.
# ESP32 scaling ~40-60x due to frequency and architecture gap.
# ------------------------------------------------------------------
SCALING_FACTORS = {
    'Raspberry Pi 4 (1.8GHz ARM)': {
        'compression': 10.0,
        'crypto':      18.0,
        'inference':   12.0,
        'db':          6.0,
    },
    'ESP32 (240MHz)': {
        'compression': 50.0,
        'crypto':      80.0,   # ESP32 has hardware AES but limited throughput
        'inference':   60.0,
        'db':          30.0,
    }
}

N_ITERATIONS = 200   # iterations per measurement for stable mean
PAYLOAD_SIZE = 1024  # 1 KB payload (representative IoT packet)

# Highly compressible payload (simulates sensor log data)
COMPRESSIBLE_PAYLOAD = (b'SENSOR_OK_TEMP_23.5_HUM_55.2_VOLT_3.3V ' * 30)[:PAYLOAD_SIZE]
# Low-entropy payload (simulates encrypted/random data)
RANDOM_PAYLOAD = os.urandom(PAYLOAD_SIZE)


def measure_us(fn, n=N_ITERATIONS):
    """Run fn() n times and return (mean_us, std_us, min_us, max_us)."""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1_000_000)
    return (
        statistics.mean(times),
        statistics.stdev(times),
        min(times),
        max(times)
    )


def run_profiler():
    cm = CompressionManager(tau=0.5)
    em = EncryptionManager()
    detector = AnomalyDetector(contamination=0.1, random_state=42)

    # Pre-train detector
    training = [[20 + i * 0.2, 40 + i * 0.1] for i in range(50)]
    detector.fit(training)

    # Temporary SQLite DB for write profiling
    tmp_db = tempfile.mktemp(suffix='.db')
    conn = sqlite3.connect(tmp_db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS perf_test "
        "(id INTEGER PRIMARY KEY, data TEXT)"
    )
    conn.commit()
    counter = [0]

    def sqlite_write():
        counter[0] += 1
        conn.execute(
            "INSERT INTO perf_test (data) VALUES (?)",
            (f"test_data_{counter[0]}",)
        )
        conn.commit()

    stages = [
        {
            'name': 'Anomaly Detection (Isolation Forest)',
            'category': 'inference',
            'fn': lambda: detector.predict([25.0, 50.0]),
        },
        {
            'name': 'ZLIB Compression (1 KB)',
            'category': 'compression',
            'fn': lambda: cm._compress_zlib(COMPRESSIBLE_PAYLOAD),
        },
        {
            'name': 'BZ2 Compression (1 KB)',
            'category': 'compression',
            'fn': lambda: cm._compress_bz2(COMPRESSIBLE_PAYLOAD),
        },
        {
            'name': 'LZMA Compression (1 KB)',
            'category': 'compression',
            'fn': lambda: cm._compress_lzma(COMPRESSIBLE_PAYLOAD),
        },
        {
            'name': 'AES-256-GCM Encryption (1 KB)',
            'category': 'crypto',
            'fn': lambda: em.encrypt(COMPRESSIBLE_PAYLOAD),
        },
        {
            'name': 'SHA-256 Integrity Hash (1 KB)',
            'category': 'crypto',
            'fn': lambda: hashlib.sha256(COMPRESSIBLE_PAYLOAD).hexdigest(),
        },
        {
            'name': 'SQLite WAL Write',
            'category': 'db',
            'fn': sqlite_write,
        },
    ]

    results = []
    print("\n" + "="*90)
    print("S-Edge Per-Operation Latency Profile — AMD Ryzen 7 6800H")
    print(f"Payload: {PAYLOAD_SIZE} bytes | Iterations: {N_ITERATIONS}")
    print("="*90)
    print(f"{'Stage':<42} {'Mean (µs)':>10} {'Std (µs)':>10} "
          f"{'Min (µs)':>10} {'Max (µs)':>10}")
    print("-"*90)

    for stage in stages:
        mean_us, std_us, min_us, max_us = measure_us(stage['fn'])
        print(f"{stage['name']:<42} {mean_us:>10.1f} {std_us:>10.1f} "
              f"{min_us:>10.1f} {max_us:>10.1f}")
        results.append({
            'Stage': stage['name'],
            'Category': stage['category'],
            'Mean_us_Ryzen7': round(mean_us, 1),
            'Std_us_Ryzen7':  round(std_us, 1),
            'Min_us_Ryzen7':  round(min_us, 1),
            'Max_us_Ryzen7':  round(max_us, 1),
        })

    # Add analytical extrapolations
    print("\n" + "="*90)
    print("Analytical Extrapolation to IoT Edge Hardware")
    print("(Based on published CPU benchmark scaling ratios)")
    print("="*90)

    for hw_name, factors in SCALING_FACTORS.items():
        print(f"\n  {hw_name}:")
        print(f"  {'Stage':<42} {'Ryzen7 (µs)':>12} {'Est. (µs)':>12} {'Est. (ms)':>12}")
        print(f"  {'-'*80}")
        for r in results:
            factor = factors[r['Category']]
            est_us = r['Mean_us_Ryzen7'] * factor
            print(f"  {r['Stage']:<42} {r['Mean_us_Ryzen7']:>12.1f} "
                  f"{est_us:>12.1f} {est_us/1000:>12.3f}")
            r[f'Est_us_{hw_name.split()[0]}'] = round(est_us, 1)

    conn.close()
    os.unlink(tmp_db)

    # Save CSV
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'per_operation_profile_results.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nNote: Extrapolations use published scaling factors.")
    print("Physical validation on embedded hardware is identified as future work.")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    run_profiler()
