"""
Shared load-balancing simulation core for comparable between table - "Load Balancing Comparison over 100 Simulation Time-Steps" / "Ablation Study: Contribution of Each S-Edge Module (Structured High-Volatility Traffic, 150 Steps)" runs.

Purpose:
- Provide a single source of truth for workload generation, S-Edge stepping,
  threshold-violation counting, oscillation counting, and synthetic CPU model.
- Prevent silent metric drift between scripts.
"""

import random
import os
import sys

# Path setup for importing multiregion modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')
for p in (parent_dir, multiregion_dir):
    if p not in sys.path:
        sys.path.append(p)

from load_balancer import LoadBalancer

# Canonical defaults (aligned to comparable experiments)
REGIONS = ['region_1', 'region_2', 'region_3']
THRESHOLD = 1000
PROCESSING_RATE = 120
SEED = 42
DURATION = 100
BURST_PROB = 0.15
BURST_EXTRA = (800, 1100)
BASE_LOAD = 50
INGRESS_REGION = 'region_1'


def generate_traffic_sequence(n=DURATION, seed=SEED, burst_prob=BURST_PROB,
                              burst_extra=BURST_EXTRA, base_load=BASE_LOAD):
    """Single-ingress step-wise workload."""
    rng = random.Random(seed)
    seq = []
    for _ in range(n):
        if rng.random() < burst_prob:
            seq.append(base_load + rng.randint(*burst_extra))
        else:
            seq.append(base_load)
    return seq


def simulated_cpu(loads, threshold=THRESHOLD):
    """Synthetic CPU proxy used by Table - "Load Balancing Comparison over 100 Simulation Time-Steps" scripts."""
    base_cpu = 55.0
    max_load = max(loads.values())
    imbalance = (max_load - min(loads.values())) / max(threshold, 1)
    cpu = (max_load / threshold) * base_cpu + imbalance * 15
    return min(cpu, 100.0)


def count_oscillation(history, target):
    """A->B->A oscillation detector."""
    if len(history) >= 2 and target == history[-2] and target != history[-1]:
        return 1
    return 0


def run_round_robin(traffic, regions=REGIONS, threshold=THRESHOLD,
                    processing_rate=PROCESSING_RATE):
    loads = {r: 0 for r in regions}
    idx = 0
    violations = 0
    flaps = 0
    history = []
    cpu_samples = []

    for t in range(len(traffic)):
        target = regions[idx]
        idx = (idx + 1) % len(regions)
        loads[target] += traffic[t]

        for r in regions:
            loads[r] = max(0, loads[r] - processing_rate)

        if any(v > threshold for v in loads.values()):
            violations += 1

        flaps += count_oscillation(history, target)
        history.append(target)
        cpu_samples.append(simulated_cpu(loads, threshold))

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return {
        'violations': violations,
        'flaps': flaps,
        'mean_cpu': mean_cpu,
        'history': history,
        'loads': loads,
    }


def run_least_connections(traffic, regions=REGIONS, threshold=THRESHOLD,
                          processing_rate=PROCESSING_RATE):
    loads = {r: 0 for r in regions}
    violations = 0
    flaps = 0
    history = []
    cpu_samples = []

    for t in range(len(traffic)):
        target = min(loads, key=loads.get)
        loads[target] += traffic[t]

        for r in regions:
            loads[r] = max(0, loads[r] - processing_rate)

        if any(v > threshold for v in loads.values()):
            violations += 1

        flaps += count_oscillation(history, target)
        history.append(target)
        cpu_samples.append(simulated_cpu(loads, threshold))

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return {
        'violations': violations,
        'flaps': flaps,
        'mean_cpu': mean_cpu,
        'history': history,
        'loads': loads,
    }


def run_sedge_lb_only(traffic, regions=REGIONS, threshold=THRESHOLD,
                      processing_rate=PROCESSING_RATE, alpha=0.7,
                      ingress=INGRESS_REGION):
    """
    Canonical S-Edge load-balancing engine used by both comparable tables.

    Semantics (single source of truth):
    - One ingress stream per step.
    - Route decision uses LoadBalancer.get_target_region(ingress).
    - Apply update_load(target, traffic[t]) then simulate_processing().
    - Violation counted once per step if ANY region exceeds threshold.
    - Redirect counted when target != ingress.
    - Net cost: 50ms per redirect (aligned with ablation assumptions).
    - Oscillation: A->B->A on target history.
    """
    lb = LoadBalancer(regions, alpha=alpha, load_threshold=threshold)

    violations = 0
    redirects = 0
    flaps = 0
    history = []
    cpu_samples = []

    for t in range(len(traffic)):
        target = lb.get_target_region(ingress)
        if target != ingress:
            redirects += 1

        lb.update_load(target, traffic[t])
        lb.simulate_processing(processing_rate)

        with lb.lock:
            if any(v > threshold for v in lb.region_loads.values()):
                violations += 1
            cpu_samples.append(simulated_cpu(dict(lb.region_loads), threshold))

        flaps += count_oscillation(history, target)
        history.append(target)

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return {
        'violations': violations,
        'flaps': flaps,
        'mean_cpu': mean_cpu,
        'redirects': redirects,
        'net_cost_ms': round(redirects * 50.0),
        'history': history,
        'final_loads': dict(lb.region_loads),
    }
