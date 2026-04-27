"""
ablation_study_comparable.py

Synchronized Table "Ablation Study: Contribution of Each S-Edge Module (Structured High-Volatility Traffic, 150 Steps)" rerun using the SAME workload model and violation
counting semantics as benchmark/gen_lb_table_comparable.py.

Why this exists:
- Previous Table "Ablation Study: Contribution of Each S-Edge Module (Structured High-Volatility Traffic, 150 Steps)" used per-region load injection and per-region violation counts.
- Comparable Table "Load Balancing Comparison over 100 Simulation Time-Steps" uses one ingress stream and step-wise violation counts.
- This script aligns Tables so numbers are directly comparable.
"""

import csv
import json
import os
import random
import sys
from datetime import datetime

from compression_manager import CompressionManager, CompressionType
from anomaly_detector import AnomalyDetector

# Import shared LB simulation core to keep both tables perfectly aligned
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
benchmark_dir = os.path.join(parent_dir, 'benchmark')
for p in (parent_dir, benchmark_dir):
    if p not in sys.path:
        sys.path.append(p)

from lb_shared_engine import (
    REGIONS,
    THRESHOLD,
    PROCESSING_RATE,
    SEED,
    DURATION,
    BURST_PROB,
    BURST_EXTRA,
    BASE_LOAD,
    INGRESS_REGION,
    generate_traffic_sequence,
    run_sedge_lb_only,
)

# ----------------------------------------------------------------------
# Aligned parameters come from benchmark/lb_shared_engine.py
# ----------------------------------------------------------------------
N_STEPS = DURATION
ANOMALY_PROB = 0.10

SYSTEM_LOG = "SYSTEM_STATUS_OK_CHECK_SENSOR_VOLTAGE_STABLE_ " * 5000


def make_normal_payload(rng):
    summary = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "temperature": round(rng.uniform(20.0, 30.0), 2),
        "humidity": round(rng.uniform(40.0, 60.0), 2),
        "priority": "low",
    }
    return json.dumps(summary).encode('utf-8')


def make_anomaly_payload(rng):
    raw_readings = []
    for _ in range(5):
        raw_readings.append({
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "temperature": round(rng.uniform(33.0, 40.0), 2),
            "humidity": round(rng.uniform(15.0, 25.0), 2),
            "system_log": SYSTEM_LOG,
        })

    summary = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "temperature": round(sum(r['temperature'] for r in raw_readings) / 5, 2),
        "humidity": round(sum(r['humidity'] for r in raw_readings) / 5, 2),
        "priority": "high",
        "raw_readings": raw_readings,
    }
    return json.dumps(summary).encode('utf-8')


def run_condition(condition_name, use_anomaly_branch=True, alpha=0.7, seed=SEED):
    rng = random.Random(seed)
    cm = CompressionManager(tau=0.5)
    detector = AnomalyDetector(contamination=0.1, random_state=seed)

    # Warm-up train anomaly detector for deterministic behavior
    train = [[20 + rng.uniform(0, 10), 40 + rng.uniform(0, 20)] for _ in range(50)]
    detector.fit(train)

    traffic = generate_traffic_sequence(N_STEPS, seed, BURST_PROB, BURST_EXTRA, BASE_LOAD)

    # Use shared engine so violation/redirect/oscillation semantics
    # are IDENTICAL to comparable Table "Load Balancing Comparison over 100 Simulation Time-Steps".
    lb_metrics = run_sedge_lb_only(
        traffic,
        regions=REGIONS,
        threshold=THRESHOLD,
        processing_rate=PROCESSING_RATE,
        alpha=alpha,
        ingress=INGRESS_REGION,
    )

    lzma_activations = 0
    anomaly_output_sizes = []

    for t in range(N_STEPS):
        # Generate anomaly/normal signal
        is_anomaly = rng.random() < ANOMALY_PROB
        sensor = [37.5, 17.0] if is_anomaly else [20 + rng.uniform(0, 10), 40 + rng.uniform(0, 20)]

        pred = detector.predict(sensor)
        detector.update(sensor)

        # Build payload and choose priority policy
        if is_anomaly:
            payload = make_anomaly_payload(rng)
        else:
            payload = make_normal_payload(rng)

        if use_anomaly_branch and pred == -1:
            priority = 'high'
        else:
            priority = 'normal'

        compressed, algo, _ = cm.adaptive_compress(payload, priority=priority)

        # Track anomaly-output size and LZMA activations
        if is_anomaly:
            anomaly_output_sizes.append(len(compressed))
        if algo == CompressionType.LZMA:
            lzma_activations += 1

    mean_anomaly_output = round(sum(anomaly_output_sizes) / len(anomaly_output_sizes)) if anomaly_output_sizes else 0

    return {
        'Condition': condition_name,
        'Violations': lb_metrics['violations'],
        'Redirects': lb_metrics['redirects'],
        'Oscillations': lb_metrics['flaps'],
        'Net. Cost (ms)': lb_metrics['net_cost_ms'],
        'LZMA Acts.': lzma_activations,
        'Anomaly Output (B)': mean_anomaly_output,
    }


def main():
    conditions = [
        dict(condition_name='S-Edge FULL', use_anomaly_branch=True, alpha=0.7),
        dict(condition_name='No Anomaly Branch', use_anomaly_branch=False, alpha=0.7),
        dict(condition_name='No Hysteresis (alpha=1.0)', use_anomaly_branch=True, alpha=1.0),
    ]

    print('=' * 110)
    print('TABLE 8 (SYNCHRONIZED) — Ablation Study over 100 Steps')
    print(f'Workload aligned to comparable Table 6: seed={SEED}, burst_prob={BURST_PROB}, burst_extra={BURST_EXTRA}')
    print('=' * 110)

    results = []
    for cond in conditions:
        print(f"Running: {cond['condition_name']}...")
        results.append(run_condition(**cond))

    headers = ['Condition', 'Violations', 'Redirects', 'Oscillations', 'Net. Cost (ms)', 'LZMA Acts.', 'Anomaly Output (B)']

    # Console table
    widths = [max(len(h), max(len(str(r[h])) for r in results)) + 2 for h in headers]
    sep = '+-' + '-+-'.join('-' * w for w in widths) + '-+'

    print('\n' + sep)
    print('| ' + ' | '.join(h.ljust(w) for h, w in zip(headers, widths)) + ' |')
    print(sep)
    for r in results:
        print('| ' + ' | '.join(str(r[h]).ljust(w) for h, w in zip(headers, widths)) + ' |')
    print(sep)

    out_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ablation_study_results_comparable.csv')
    with open(out_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)

    print(f'\nSaved CSV: {out_csv}')


if __name__ == '__main__':
    main()
