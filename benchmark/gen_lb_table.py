"""
Generate Table 3 – Load Balancing Comparison over 100 Simulation Time-Steps
Compares: Round-Robin  |  Least Connections  |  S-Edge (proposed)
Metrics : Threshold violations, Load-flapping events, Mean CPU utilization
"""

import random
import sys
import os
import time
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')
for p in (parent_dir, multiregion_dir):
    if p not in sys.path:
        sys.path.append(p)

from load_balancer import LoadBalancer

# --- CONFIGURATION ---
REGIONS        = ['region_1', 'region_2', 'region_3']
DURATION       = 100        # time-steps
THRESHOLD      = 1000       # same as LoadBalancer.load_threshold
PROCESSING_RATE = 120       # units drained per region per step
SEED           = 42         # reproducible traffic

# --------------------------------------------------------------------------
#  Traffic generator (deterministic across all three strategies)
# --------------------------------------------------------------------------
def generate_traffic_sequence(n, seed):
    """Return a list of n traffic values (bursty IoT pattern)."""
    rng = random.Random(seed)
    seq = []
    for _ in range(n):
        r = rng.random()
        if r < 0.10:                     # 10 % extreme burst (video / batch)
            seq.append(rng.randint(800, 1200))
        elif r < 0.30:                   # 20 % moderate burst
            seq.append(rng.randint(300, 600))
        else:                            # 70 % light sensor data
            seq.append(rng.randint(10, 80))
    return seq

def simulated_cpu(loads, threshold):
    """Estimate CPU utilisation from the load distribution.
    Model: CPU% = (max_region_load / threshold) * BASE, clamped to 100.
    Regions under heavier / more uneven load ≈ higher CPU."""
    BASE_CPU = 55.0           # peak when a region hits the threshold
    max_load = max(loads.values())
    imbalance = (max(loads.values()) - min(loads.values())) / max(threshold, 1)
    cpu = (max_load / threshold) * BASE_CPU + imbalance * 15
    return min(cpu, 100.0)

traffic = generate_traffic_sequence(DURATION, SEED)

# --------------------------------------------------------------------------
#  Strategy helpers
# --------------------------------------------------------------------------

def run_round_robin():
    """Pure round-robin: cycle through regions regardless of load."""
    loads = {r: 0 for r in REGIONS}
    violations = 0
    idx = 0
    flaps = 0                       # N/A for round-robin but count anyway

    target_history = []
    cpu_samples = []
    for t in range(DURATION):
        target = REGIONS[idx]
        idx = (idx + 1) % len(REGIONS)

        loads[target] += traffic[t]

        # simulate processing
        for r in REGIONS:
            loads[r] = max(0, loads[r] - PROCESSING_RATE)

        # threshold check (any region over?)
        if any(v > THRESHOLD for v in loads.values()):
            violations += 1

        # flapping = oscillation (A→B→A pattern)
        if len(target_history) >= 2 and target == target_history[-2] and target != target_history[-1]:
            flaps += 1
        target_history.append(target)

        cpu_samples.append(simulated_cpu(loads, THRESHOLD))

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return violations, flaps, mean_cpu


def run_least_connections():
    """Least-connections: always pick the region with the lowest current load
    (no hysteresis, no redistribution)."""
    loads = {r: 0 for r in REGIONS}
    violations = 0
    flaps = 0
    target_history = []

    cpu_samples = []
    for t in range(DURATION):
        # pick region with min load
        target = min(loads, key=loads.get)

        loads[target] += traffic[t]

        # simulate processing
        for r in REGIONS:
            loads[r] = max(0, loads[r] - PROCESSING_RATE)

        # threshold check
        if any(v > THRESHOLD for v in loads.values()):
            violations += 1

        # flapping = oscillation (A→B→A pattern)
        if len(target_history) >= 2 and target == target_history[-2] and target != target_history[-1]:
            flaps += 1
        target_history.append(target)

        cpu_samples.append(simulated_cpu(loads, THRESHOLD))

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return violations, flaps, mean_cpu


def run_sedge():
    """S-Edge: uses the project's LoadBalancer with threshold-based
    redistribution and hysteresis."""
    lb = LoadBalancer(REGIONS)
    violations = 0
    flaps = 0
    target_history = []

    cpu_samples = []
    for t in range(DURATION):
        # region_1 is the default ingress point
        ingress = REGIONS[0]

        # S-Edge routing decision
        current_load = lb.region_loads[ingress]
        optimal = lb.get_optimal_region()
        if optimal != ingress and lb.region_loads[optimal] < current_load * 0.7:
            target = optimal
        else:
            target = ingress

        lb.update_load(target, traffic[t])
        lb.simulate_processing(PROCESSING_RATE)

        # threshold check
        with lb.lock:
            if any(v > THRESHOLD for v in lb.region_loads.values()):
                violations += 1

        # flapping = oscillation (A→B→A pattern)
        if len(target_history) >= 2 and target == target_history[-2] and target != target_history[-1]:
            flaps += 1
        target_history.append(target)

        with lb.lock:
            cpu_samples.append(simulated_cpu(dict(lb.region_loads), THRESHOLD))

    mean_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
    return violations, flaps, mean_cpu


# --------------------------------------------------------------------------
#  Run all three strategies
# --------------------------------------------------------------------------
print("Running load-balancing comparison (100 time-steps) …\n")

rr_violations,  rr_flaps,  rr_cpu  = run_round_robin()
lc_violations,  lc_flaps,  lc_cpu  = run_least_connections()
se_violations,  se_flaps,  se_cpu  = run_sedge()

# --------------------------------------------------------------------------
#  Console table
# --------------------------------------------------------------------------
header = f"{'Metric':<28} {'Round-Robin':>14} {'Least Conn.':>14} {'S-Edge':>14}"
sep    = "-" * len(header)
print(sep)
print(header)
print(sep)
print(f"{'Threshold violations':<28} {rr_violations:>10}/100 {lc_violations:>10}/100 {se_violations:>10}/100")
print(f"{'Load-flapping events':<28} {'N/A':>14} {lc_flaps:>14} {se_flaps:>14}")
print(f"{'Mean CPU utilization':<28} {rr_cpu:>13.1f}% {lc_cpu:>13.1f}% {se_cpu:>13.1f}%")
print(sep)

# --------------------------------------------------------------------------
#  Matplotlib table (saved as PNG)
# --------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 3))
ax.axis('off')

col_labels = ['Metric', 'Round-Robin', 'Least Connections', 'S-Edge']
table_data = [
    ['Threshold violations',
     f'{rr_violations}/100', f'{lc_violations}/100', f'{se_violations}/100'],
    ['Load-flapping events',
     'N/A', str(lc_flaps), str(se_flaps)],
    ['Mean CPU utilization',
     f'~{rr_cpu:.1f}%', f'~{lc_cpu:.1f}%', f'~{se_cpu:.1f}%'],
]

tbl = ax.table(cellText=table_data,
               colLabels=col_labels,
               loc='center',
               cellLoc='center')

tbl.auto_set_font_size(False)
tbl.set_fontsize(11)
tbl.scale(1.2, 1.6)

# Style header row
for j in range(len(col_labels)):
    cell = tbl[0, j]
    cell.set_facecolor('#4472C4')
    cell.set_text_props(color='white', fontweight='bold')

# Alternate row shading
for i in range(1, len(table_data) + 1):
    for j in range(len(col_labels)):
        cell = tbl[i, j]
        cell.set_facecolor('#D9E2F3' if i % 2 == 0 else 'white')

ax.set_title('Table 3  Load Balancing Comparison over 100 Simulation Time-Steps',
             fontsize=13, fontweight='bold', pad=20)

plt.tight_layout()
out_path = os.path.join(current_dir, 'load_balancing_table.png')
plt.savefig(out_path, dpi=300, bbox_inches='tight')
print(f"\nTable image saved → {out_path}")
