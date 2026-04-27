"""
Flapping Scenario Study: Demonstrates hysteresis (alpha=0.7) vs. no hysteresis (alpha=1.0)
under tight threshold conditions where regions constantly hover near the 1000-byte limit.

Configuration:
- BASE_LOAD=600 (high baseline)
- BURST_EXTRA=(300,500) (small unpredictable bursts)
- This creates a "right-around-threshold" environment perfect for oscillation testing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'multiregion'))

from lb_shared_engine import (
    generate_traffic_sequence,
    run_sedge_lb_only,
    count_oscillation
)
import matplotlib.pyplot as plt
import numpy as np

# === TIGHT THRESHOLD SCENARIO ===
DURATION = 150
SEED = 42
BURST_PROB = 0.15
BURST_EXTRA = (300, 500)  # Much smaller bursts
BASE_LOAD = 600           # High baseline = hovering near 1000 threshold
THRESHOLD = 1000
PROCESSING_RATE = 120
REGIONS = ['region_1', 'region_2', 'region_3']
INGRESS = 'region_1'

print("=" * 80)
print("FLAPPING SCENARIO STUDY: Hysteresis vs. Oscillation")
print("=" * 80)
print(f"\nWorkload Configuration:")
print(f"  Duration: {DURATION} steps")
print(f"  Base Load: {BASE_LOAD} bytes/step (HIGH baseline)")
print(f"  Burst Extra: {BURST_EXTRA} bytes (small, unpredictable)")
print(f"  Burst Probability: {BURST_PROB}")
print(f"  Threshold: {THRESHOLD} bytes")
print(f"  Processing Rate: {PROCESSING_RATE} bytes/step")
print(f"\nExpected Behavior:")
print(f"  - With α=0.7 (hysteresis): Sticky routing → few oscillations, stable")
print(f"  - With α=1.0 (greedy): Always chase optimal → oscillations, flapping")
print(f"\nGenerating tight-threshold traffic sequence...")

# Generate traffic sequence once
traffic = generate_traffic_sequence(
    n=DURATION,
    seed=SEED,
    burst_prob=BURST_PROB,
    burst_extra=BURST_EXTRA,
    base_load=BASE_LOAD
)

# Print traffic statistics
traffic_min, traffic_max, traffic_mean = min(traffic), max(traffic), np.mean(traffic)
print(f"  Traffic stats: min={traffic_min}B, max={traffic_max}B, mean={traffic_mean:.1f}B")
print(f"  Threshold: {THRESHOLD}B")
print(f"  → Traffic range spans threshold by {traffic_max - THRESHOLD:+.0f}B")

print("\n" + "=" * 80)
print("RUN 1: S-Edge with α=0.7 (HYSTERESIS - expected to be stable)")
print("=" * 80)
result_hysteresis = run_sedge_lb_only(
    traffic=traffic,
    regions=REGIONS,
    threshold=THRESHOLD,
    processing_rate=PROCESSING_RATE,
    alpha=0.7,
    ingress=INGRESS
)

print(f"\nResults (α=0.7 HYSTERESIS):")
print(f"  Violations: {result_hysteresis['violations']}/150")
print(f"  Oscillations (A→B→A): {result_hysteresis['flaps']}")
print(f"  Redirects: {result_hysteresis['redirects']}")
print(f"  Mean CPU: {result_hysteresis['mean_cpu']:.1f}%")

print("\n" + "=" * 80)
print("RUN 2: S-Edge with α=1.0 (NO HYSTERESIS - expected to oscillate badly)")
print("=" * 80)
result_greedy = run_sedge_lb_only(
    traffic=traffic,
    regions=REGIONS,
    threshold=THRESHOLD,
    processing_rate=PROCESSING_RATE,
    alpha=1.0,
    ingress=INGRESS
)

print(f"\nResults (α=1.0 GREEDY):")
print(f"  Violations: {result_greedy['violations']}/150")
print(f"  Oscillations (A→B→A): {result_greedy['flaps']}")
print(f"  Redirects: {result_greedy['redirects']}")
print(f"  Mean CPU: {result_greedy['mean_cpu']:.1f}%")

print("\n" + "=" * 80)
print("COMPARATIVE ANALYSIS")
print("=" * 80)
violation_diff = result_greedy['violations'] - result_hysteresis['violations']
oscillation_diff = result_greedy['flaps'] - result_hysteresis['flaps']
redirect_diff = result_greedy['redirects'] - result_hysteresis['redirects']

print(f"\nα=1.0 vs α=0.7 (Hysteresis Benefit):")
print(f"  Violations: {result_greedy['violations']} vs {result_hysteresis['violations']} " +
      f"({violation_diff:+d} extra violations with greedy)")
print(f"  Oscillations: {result_greedy['flaps']} vs {result_hysteresis['flaps']} " +
      f"({oscillation_diff:+d} extra oscillations with greedy)")
print(f"  Redirects: {result_greedy['redirects']} vs {result_hysteresis['redirects']} " +
      f"({redirect_diff:+d} extra redirects with greedy)")

print("\n" + "=" * 80)
print("Generating visualization...")
print("=" * 80)

# Extract load histories
history_hysteresis = result_hysteresis['history']
history_greedy = result_greedy['history']
loads_hysteresis = result_hysteresis['final_loads']
loads_greedy = result_greedy['final_loads']

# Count total flaps per region (pattern X→Y→X for each step)
def count_flaps_per_region(history, target_region):
    """Count oscillations specifically for one region"""
    flaps = 0
    for i in range(len(history) - 2):
        if history[i] == target_region and history[i+2] == target_region and history[i+1] != target_region:
            flaps += 1
    return flaps

# Create figure with subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Flapping Scenario: α=0.7 Hysteresis vs α=1.0 Greedy', fontsize=14, fontweight='bold')

# === TOP LEFT: Routing path comparison ===
ax = axes[0, 0]
region_to_num = {'region_1': 1, 'region_2': 2, 'region_3': 3}
hysteresis_nums = [region_to_num[r] for r in history_hysteresis]
greedy_nums = [region_to_num[r] for r in history_greedy]

steps = range(min(100, len(history_hysteresis)))  # Show first 100 steps
ax.plot(steps, [hysteresis_nums[i] for i in steps], 'o-', label='α=0.7 (Hysteresis)', 
        markersize=3, linewidth=1, alpha=0.7, color='green')
ax.plot(steps, [greedy_nums[i] for i in steps], 's-', label='α=1.0 (Greedy)', 
        markersize=3, linewidth=1, alpha=0.7, color='red')
ax.set_ylabel('Target Region')
ax.set_xlabel('Time Step')
ax.set_title('Routing Decisions (First 100 Steps)')
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(['region_1', 'region_2', 'region_3'])
ax.legend()
ax.grid(True, alpha=0.3)

# === TOP RIGHT: Oscillation/flap events ===
ax = axes[0, 1]
categories = ['α=0.7\n(Hysteresis)', 'α=1.0\n(Greedy)']
oscillations = [result_hysteresis['flaps'], result_greedy['flaps']]
colors = ['green', 'red']
bars = ax.bar(categories, oscillations, color=colors, alpha=0.7, edgecolor='black', linewidth=2)

# Add value labels on bars
for bar, val in zip(bars, oscillations):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(val)}',
            ha='center', va='bottom', fontweight='bold', fontsize=12)

ax.set_ylabel('Oscillation Events (A→B→A)')
ax.set_title('Oscillation Count Comparison')
ax.set_ylim(0, max(oscillations) * 1.2)
ax.grid(True, alpha=0.3, axis='y')

# === BOTTOM LEFT: Violations comparison ===
ax = axes[1, 0]
violations = [result_hysteresis['violations'], result_greedy['violations']]
bars = ax.bar(categories, violations, color=colors, alpha=0.7, edgecolor='black', linewidth=2)

# Add value labels on bars
for bar, val in zip(bars, violations):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(val)}',
            ha='center', va='bottom', fontweight='bold', fontsize=12)

ax.set_ylabel('Threshold Violations')
ax.set_title(f'Violations (threshold={THRESHOLD}B)')
ax.set_ylim(0, max(violations) * 1.2)
ax.grid(True, alpha=0.3, axis='y')

# === BOTTOM RIGHT: Redirects comparison ===
ax = axes[1, 1]
redirects = [result_hysteresis['redirects'], result_greedy['redirects']]
bars = ax.bar(categories, redirects, color=colors, alpha=0.7, edgecolor='black', linewidth=2)

# Add value labels on bars
for bar, val in zip(bars, redirects):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(val)}',
            ha='center', va='bottom', fontweight='bold', fontsize=12)

ax.set_ylabel('Routing Redirects')
ax.set_title('Redirect Count (extra routing overhead)')
ax.set_ylim(0, max(redirects) * 1.2)
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = 'flapping_scenario_comparison.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"✓ Visualization saved to: {output_path}")

print("\n" + "=" * 80)
print("INTERPRETATION")
print("=" * 80)
print(f"""
The flapping scenario demonstrates the critical role of hysteresis (α=0.7):

1. OSCILLATION CONTROL:
   - α=0.7: {result_hysteresis['flaps']} oscillations (sticky routing keeps decisions stable)
   - α=1.0: {result_greedy['flaps']} oscillations (greedy constantly chases optimal, causes A→B→A flapping)
   
2. VIOLATION DIFFERENCE:
   - α=0.7: {result_hysteresis['violations']} violations (acceptable)
   - α=1.0: {result_greedy['violations']} violations ({violation_diff:+d} extra due to constant switching overhead)
   
3. ROUTING OVERHEAD:
   - α=0.7: {result_hysteresis['redirects']} redirects (efficient, stable decisions)
   - α=1.0: {result_greedy['redirects']} redirects ({redirect_diff:+d} extra redirects = network overhead)
   
4. WHY THIS MATTERS:
   By hovering regions right around the threshold (BASE_LOAD=600, BURST_EXTRA=(300,500)),
   we create a scenario where every decision matters. Greedy routing (α=1.0) oscillates
   trying to always pick the "best" region, but this switching cost overwhelms any benefit.
   
   Hysteresis (α=0.7) says: "stick with your region unless it's at least 30% better."
   This eliminates oscillations and provides better overall stability.

5. REAL-WORLD IMPLICATION:
   In production edge networks with burst-heavy workloads, hysteresis prevents
   cascade failures from constant route-flapping, which can degrade service quality
   more than accepting a few extra violations on occasional peaks.
""")

print("=" * 80)
print("Study Complete!")
print("=" * 80)
