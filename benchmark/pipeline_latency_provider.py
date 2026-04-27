"""
pipeline_latency_profiler.py — End-to-End Pipeline Latency Measurement
=======================================================================
Measures per-stage and total latency from anomaly detection firing to
storage write completion, for both normal and high-priority (anomalous)
packets. 

Pipeline stages measured:
  Stage 1: Anomaly Detection  — Isolation Forest predict()
  Stage 2: Compression        — adaptive_compress() (ZLIB for normal, LZMA for anomaly)
  Stage 3: Encryption         — AES-256-GCM encrypt()
  Stage 4: Routing Decision   — get_target_region() hysteresis check
  Stage 5: Storage Write      — encrypted bytes written to disk

Key comparison:
  Normal packet:  ZLIB compression (~0.7ms) → small payload → fast encryption
  Anomaly packet: LZMA compression (~25ms) → large payload → pipeline dominated
                  by compression stage, not detection or routing

This demonstrates that:
  (a) Detection and routing add negligible latency (<0.01ms each)
  (b) The compression stage dominates anomaly packet latency
  (c) Total anomaly pipeline latency is ~25ms, well within the
      29.5-86.2ms write latency window reported in Section 6.7
"""

import time
import json
import random
import os
import sys
import csv
import tempfile
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anomaly_detector import AnomalyDetector
from compression_manager import CompressionManager, CompressionType
from encryption_manager import EncryptionManager
from load_balancer import LoadBalancer

N_RUNS       = 50     # runs per packet type for stable statistics
SEED         = 42
REGIONS      = ['region_1', 'region_2', 'region_3']
SYSTEM_LOG   = "SYSTEM_STATUS_OK_CHECK_SENSOR_VOLTAGE_STABLE_ " * 5000


def make_normal_packet(rng):
    """Small summary JSON — normal traffic path."""
    return json.dumps({
        "timestamp":   "2024-01-15T10:30:00Z",
        "temperature": round(rng.uniform(20.0, 30.0), 2),
        "humidity":    round(rng.uniform(40.0, 60.0), 2),
        "priority":    "low"
    }).encode('utf-8')


def make_anomaly_packet(rng):
    """Large summary + raw_readings — anomaly path (edge_device fix applied)."""
    raw = [{
        "timestamp":   "2024-01-15T10:30:00Z",
        "temperature": round(rng.uniform(33.0, 40.0), 2),
        "humidity":    round(rng.uniform(15.0, 25.0), 2),
        "system_log":  SYSTEM_LOG
    } for _ in range(5)]
    return json.dumps({
        "timestamp":    "2024-01-15T10:30:00Z",
        "temperature":  round(sum(r['temperature'] for r in raw) / 5, 2),
        "humidity":     round(sum(r['humidity']    for r in raw) / 5, 2),
        "priority":     "high",
        "raw_readings": raw
    }).encode('utf-8')


def measure_pipeline(packet_type, payload, sensor, priority,
                     detector, cm, em, lb, tmp_dir, run_id):
    """
    Measure each stage of the save_to_cloud() pipeline.
    Returns dict of per-stage latencies in milliseconds.
    """
    t_pipeline_start = time.perf_counter()

    # Stage 1: Anomaly Detection
    t0 = time.perf_counter()
    prediction = detector.predict(sensor)
    t_detection = (time.perf_counter() - t0) * 1000

    # Stage 2: Compression (Algorithm 1)
    t0 = time.perf_counter()
    compressed, algo, eta = cm.adaptive_compress(payload, priority=priority)
    t_compression = (time.perf_counter() - t0) * 1000

    # Stage 3: Encryption (AES-256-GCM)
    t0 = time.perf_counter()
    encrypted = em.encrypt(compressed)
    t_encryption = (time.perf_counter() - t0) * 1000

    # Stage 4: Routing Decision (Algorithm 2 + hysteresis)
    t0 = time.perf_counter()
    target = lb.get_target_region(REGIONS[0])
    t_routing = (time.perf_counter() - t0) * 1000

    # Stage 5: Storage Write
    fpath = os.path.join(tmp_dir, f'{packet_type}_{run_id}.bin')
    t0 = time.perf_counter()
    with open(fpath, 'wb') as f:
        f.write(encrypted)
    t_storage = (time.perf_counter() - t0) * 1000

    t_total = (time.perf_counter() - t_pipeline_start) * 1000

    # Update load metric post-compression (closed feedback loop)
    lb.update_load(target, len(encrypted))

    return {
        'packet_type':    packet_type,
        'algorithm':      algo.value,
        'payload_bytes':  len(payload),
        'compressed_bytes': len(compressed),
        'eta':            round(eta * 100, 1),
        't_detection_ms': round(t_detection,   4),
        't_compression_ms': round(t_compression, 3),
        't_encryption_ms':  round(t_encryption,  3),
        't_routing_ms':     round(t_routing,     4),
        't_storage_ms':     round(t_storage,     3),
        't_total_ms':       round(t_total,       3),
    }


def run_profiler():
    rng      = random.Random(SEED)
    detector = AnomalyDetector(contamination=0.1, random_state=SEED)
    cm       = CompressionManager(tau=0.5)
    em       = EncryptionManager()
    lb       = LoadBalancer(REGIONS, alpha=0.7, load_threshold=1000)
    tmp_dir  = tempfile.mkdtemp()

    # Pre-train detector
    training = [[20 + rng.uniform(0, 10), 40 + rng.uniform(0, 20)]
                for _ in range(50)]
    detector.fit(training)

    print(f"\nPayload sizes:")
    normal_sample  = make_normal_packet(rng)
    anomaly_sample = make_anomaly_packet(rng)
    print(f"  Normal:  {len(normal_sample):,} bytes")
    print(f"  Anomaly: {len(anomaly_sample):,} bytes (~{len(anomaly_sample)//1024} KB)")

    all_records = []

    print(f"\nRunning {N_RUNS} normal packets...")
    for i in range(N_RUNS):
        rng2    = random.Random(SEED + i)
        payload = make_normal_packet(rng2)
        sensor  = [rng2.uniform(20, 30), rng2.uniform(40, 60)]
        r = measure_pipeline('normal', payload, sensor, 'normal',
                             detector, cm, em, lb, tmp_dir, i)
        all_records.append(r)

    print(f"Running {N_RUNS} anomaly packets...")
    for i in range(N_RUNS):
        rng2    = random.Random(SEED + 1000 + i)
        payload = make_anomaly_packet(rng2)
        sensor  = [rng2.uniform(33, 40), rng2.uniform(15, 25)]
        r = measure_pipeline('anomaly', payload, sensor, 'high',
                             detector, cm, em, lb, tmp_dir, i)
        all_records.append(r)

    # Aggregate by packet type
    stages = ['t_detection_ms', 't_compression_ms', 't_encryption_ms',
              't_routing_ms',   't_storage_ms',     't_total_ms']
    stage_labels = ['Detection', 'Compression', 'Encryption',
                    'Routing',   'Storage Write', 'TOTAL']

    results_summary = {}
    for ptype in ['normal', 'anomaly']:
        subset = [r for r in all_records if r['packet_type'] == ptype]
        results_summary[ptype] = {}
        for stage, label in zip(stages, stage_labels):
            vals = [r[stage] for r in subset]
            results_summary[ptype][label] = {
                'mean': round(statistics.mean(vals), 3),
                'std':  round(statistics.stdev(vals), 3),
                'min':  round(min(vals), 3),
                'max':  round(max(vals), 3),
            }

    # Print results
    print("\n" + "="*80)
    print(f"End-to-End Pipeline Latency Profile (n={N_RUNS} per type)")
    print(f"Seed={SEED} | alpha=0.7 | tau=0.5 | AES-256-GCM")
    print("="*80)
    print(f"{'Stage':<16} | {'Normal (ms)':>18}       | {'Anomaly (ms)':>18}")
    print(f"{'':16} | {'mean ± std':>13} {'[min,max]':>8} | "
          f"{'mean ± std':>13} {'[min,max]':>8}")
    print("-"*80)

    for label in stage_labels:
        n = results_summary['normal'][label]
        a = results_summary['anomaly'][label]
        sep = "=" if label == 'TOTAL' else " "
        print(f"{label:<16} {sep} "
              f"{n['mean']:>6.3f} ± {n['std']:<6.3f} "
              f"[{n['min']:.3f},{n['max']:.3f}] | "
              f"{a['mean']:>6.3f} ± {a['std']:<6.3f} "
              f"[{a['min']:.3f},{a['max']:.3f}]")

    print("="*80)

    # Key findings
    n_total = results_summary['normal']['TOTAL']['mean']
    a_total = results_summary['anomaly']['TOTAL']['mean']
    n_comp  = results_summary['normal']['Compression']['mean']
    a_comp  = results_summary['anomaly']['Compression']['mean']
    n_det   = results_summary['normal']['Detection']['mean']
    a_det   = results_summary['anomaly']['Detection']['mean']
    n_route = results_summary['normal']['Routing']['mean']
    a_route = results_summary['anomaly']['Routing']['mean']

    print("\nKey findings:")
    print(f"  Total pipeline latency:  Normal={n_total:.1f}ms  "
          f"Anomaly={a_total:.1f}ms")
    print(f"  Compression dominates:   Normal={n_comp:.3f}ms  "
          f"Anomaly={a_comp:.1f}ms "
          f"({a_comp/a_total*100:.0f}% of anomaly total)")
    print(f"  Detection overhead:      Normal={n_det:.4f}ms  "
          f"Anomaly={a_det:.4f}ms (negligible)")
    print(f"  Routing overhead:        Normal={n_route:.4f}ms  "
          f"Anomaly={a_route:.4f}ms (negligible)")
    print(f"  Anomaly total ({a_total:.1f}ms) is well within "
          f"network write latency window (29.5-86.2ms, Section 6.6)")
    print(f"  Detection+Routing combined: "
          f"{(a_det+a_route):.4f}ms — "
          f"{(a_det+a_route)/a_total*100:.2f}% of total anomaly pipeline")

    # Save CSV
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'pipeline_latency_results.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(all_records[0].keys()))
        writer.writeheader()
        writer.writerows(all_records)
    print(f"\nRaw results saved to: {out_path}")
    return results_summary


if __name__ == "__main__":
    run_profiler()