"""
Enhanced Flapping Scenario Study with detailed routing analysis
This version shows minute-by-minute routing patterns to visualize oscillation behavior
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'multiregion'))

from lb_shared_engine import generate_traffic_sequence
from multiregion.load_balancer import LoadBalancer
import matplotlib.pyplot as plt
import numpy as np

# === EVEN TIGHTER THRESHOLD SCENARIO ===
DURATION = 150
SEED = 42
BURST_PROB = 0.12
BURST_EXTRA = (200, 350)  # VERY small bursts
BASE_LOAD = 750           # Even higher baseline
THRESHOLD = 1000
PROCESSING_RATE = 120
REGIONS = ['region_1', 'region_2', 'region_3']
INGRESS = 'region_1'

print("=" * 90)
print("ENHANCED FLAPPING SCENARIO: Sweet Spot for Hysteresis Benefit")
print("=" * 90)
print(f"\nWorkload Configuration:")
print(f"  Duration: {DURATION} steps")
print(f"  Base Load: {BASE_LOAD} bytes/step (very high baseline)")
print(f"  Burst Extra: {BURST_EXTRA} bytes (tiny, unpredictable)")
print(f"  Burst Probability: {BURST_PROB}")
print(f"  Threshold: {THRESHOLD} bytes")
print(f"  Processing Rate: {PROCESSING_RATE} bytes/step")
print(f"\nScenario Design Rationale:")
print(f"  Current region is JUST below threshold (750+250 avg = 1000)")
print(f"  Regions drain only 120B/step, so overload persists multi-step")
print(f"  This forces continuous routing decisions right at the threshold boundary")

# Generate traffic
traffic = generate_traffic_sequence(
    n=DURATION,
    seed=SEED,
    burst_prob=BURST_PROB,
    burst_extra=BURST_EXTRA,
    base_load=BASE_LOAD
)

traffic_min, traffic_max, traffic_mean = min(traffic), max(traffic), np.mean(traffic)
print(f"\nTraffic stats: min={traffic_min}B, max={traffic_max}B, mean={traffic_mean:.1f}B")
print(f"  → {traffic_mean:.0f}B mean is {1000 - traffic_mean:.0f}B {'below' if traffic_mean < 1000 else 'above'} threshold")

# === RUN 1: Alpha=0.7 (Hysteresis) ===
print("\n" + "=" * 90)
print("HYSTERESIS RUN: α=0.7 (sticky, prefer current region unless 30% better)")
print("=" * 90)

lb_hysteresis = LoadBalancer(REGIONS, alpha=0.7, load_threshold=THRESHOLD)
routing_hysteresis = []
violations_hysteresis = 0
redirects_hysteresis = 0

for t in range(DURATION):
    current_region = routing_hysteresis[-1] if routing_hysteresis else INGRESS
    target = lb_hysteresis.get_target_region(INGRESS)
    
    if target != current_region:
        redirects_hysteresis += 1
    
    lb_hysteresis.update_load(target, traffic[t])
    lb_hysteresis.simulate_processing(PROCESSING_RATE)
    
    max_load = max(lb_hysteresis.region_loads.values())
    if max_load > THRESHOLD:
        violations_hysteresis += 1
    
    routing_hysteresis.append(target)

# Count oscillations (A→B→A patterns)
oscillations_hysteresis = 0
for i in range(len(routing_hysteresis) - 2):
    if routing_hysteresis[i] == routing_hysteresis[i+2] and routing_hysteresis[i] != routing_hysteresis[i+1]:
        oscillations_hysteresis += 1

print(f"\nHysteresis Results (α=0.7):")
print(f"  Violations: {violations_hysteresis}/150")
print(f"  Redirects: {redirects_hysteresis}")
print(f"  Oscillations (A→B→A): {oscillations_hysteresis}")

# === RUN 2: Alpha=1.0 (Greedy) ===
print("\n" + "=" * 90)
print("GREEDY RUN: α=1.0 (always pick absolute optimal, no hysteresis)")
print("=" * 90)

lb_greedy = LoadBalancer(REGIONS, alpha=1.0, load_threshold=THRESHOLD)
routing_greedy = []
violations_greedy = 0
redirects_greedy = 0

for t in range(DURATION):
    current_region = routing_greedy[-1] if routing_greedy else INGRESS
    target = lb_greedy.get_target_region(INGRESS)
    
    if target != current_region:
        redirects_greedy += 1
    
    lb_greedy.update_load(target, traffic[t])
    lb_greedy.simulate_processing(PROCESSING_RATE)
    
    max_load = max(lb_greedy.region_loads.values())
    if max_load > THRESHOLD:
        violations_greedy += 1
    
    routing_greedy.append(target)

# Count oscillations
oscillations_greedy = 0
for i in range(len(routing_greedy) - 2):
    if routing_greedy[i] == routing_greedy[i+2] and routing_greedy[i] != routing_greedy[i+1]:
        oscillations_greedy += 1

print(f"\nGreedy Results (α=1.0):")
print(f"  Violations: {violations_greedy}/150")
print(f"  Redirects: {redirects_greedy}")
print(f"  Oscillations (A→B→A): {oscillations_greedy}")

# === DETAILED COMPARISON ===
print("\n" + "=" * 90)
print("COMPARATIVE METRICS")
print("=" * 90)
print(f"\nViolations:     α=0.7: {violations_hysteresis:3d}  |  α=1.0: {violations_greedy:3d}  " +
      f"│ Difference: {violations_greedy - violations_hysteresis:+3d}")
print(f"Redirects:      α=0.7: {redirects_hysteresis:3d}  |  α=1.0: {redirects_greedy:3d}  " +
      f"│ Difference: {redirects_greedy - redirects_hysteresis:+3d}")
print(f"Oscillations:   α=0.7: {oscillations_hysteresis:3d}  |  α=1.0: {oscillations_greedy:3d}  " +
      f"│ Difference: {oscillations_greedy - oscillations_hysteresis:+3d}")

# === ANALYZE ROUTING PATTERN STABILITY ===
def compute_routing_entropy(routing_sequence):
    """Compute Shannon entropy of routing decisions (low = sticky, high = chaotic)"""
    from collections import Counter
    counts = Counter(routing_sequence)
    total = len(routing_sequence)
    entropy = 0
    for count in counts.values():
        p = count / total
        entropy -= p * np.log2(p)
    return entropy

entropy_hysteresis = compute_routing_entropy(routing_hysteresis)
entropy_greedy = compute_routing_entropy(routing_greedy)

print(f"\nRouting Stability (Entropy - lower is stickier):")
print(f"  α=0.7: {entropy_hysteresis:.3f}  |  α=1.0: {entropy_greedy:.3f}")
print(f"  → α=0.7 is {'stickier' if entropy_hysteresis < entropy_greedy else 'more chaotic'}")

# === COMPUTE FLAP INTENSITY (consecutive redirects) ===
consecutive_redirects_hysteresis = 0
consecutive_redirects_greedy = 0
current_streak = 1

for i in range(1, len(routing_hysteresis)):
    if routing_hysteresis[i] != routing_hysteresis[i-1]:
        consecutive_redirects_hysteresis += 1

for i in range(1, len(routing_greedy)):
    if routing_greedy[i] != routing_greedy[i-1]:
        consecutive_redirects_greedy += 1

print(f"\nConsecutive Region Changes (flap count):")
print(f"  α=0.7: {consecutive_redirects_hysteresis}  |  α=1.0: {consecutive_redirects_greedy}")

# === VISUALIZATION ===
fig, axes = plt.subplots(2, 2, figsize=(15, 10))
fig.suptitle('Enhanced Flapping Scenario: α=0.7 vs α=1.0 Under Tight Threshold', 
             fontsize=14, fontweight='bold')

# Plot 1: First 80 steps of routing decisions
ax = axes[0, 0]
region_map = {'region_1': 1, 'region_2': 2, 'region_3': 3}
steps_to_show = 80

hyster_nums = [region_map[r] for r in routing_hysteresis[:steps_to_show]]
greedy_nums = [region_map[r] for r in routing_greedy[:steps_to_show]]

ax.plot(range(steps_to_show), hyster_nums, 'o-', label='α=0.7 (Hysteresis)', 
        markersize=4, linewidth=1.5, alpha=0.8, color='green')
ax.plot(range(steps_to_show), [g + 0.15 for g in greedy_nums], 's-', label='α=1.0 (Greedy)', 
        markersize=4, linewidth=1.5, alpha=0.8, color='red')
ax.set_ylabel('Target Region')
ax.set_xlabel('Time Step')
ax.set_title(f'Routing Decisions (First {steps_to_show} Steps)')
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(['region_1', 'region_2', 'region_3'])
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

# Plot 2: Violation count over time (cumulative)
ax = axes[0, 1]
hyster_violations_cumsum = [0]
greedy_violations_cumsum = [0]

for i in range(DURATION):
    hyster_v = hyster_violations_cumsum[-1] + (1 if violations_hysteresis > 0 else 0)
    # Recompute violations per step for both
    lb_test_h = LoadBalancer(REGIONS, alpha=0.7, load_threshold=THRESHOLD)
    lb_test_g = LoadBalancer(REGIONS, alpha=1.0, load_threshold=THRESHOLD)
    
hyster_cumsum = []
greedy_cumsum = []
hyster_count = 0
greedy_count = 0

lb_h = LoadBalancer(REGIONS, alpha=0.7, load_threshold=THRESHOLD)
lb_g = LoadBalancer(REGIONS, alpha=1.0, load_threshold=THRESHOLD)

for t in range(DURATION):
    target_h = lb_h.get_target_region(INGRESS)
    lb_h.update_load(target_h, traffic[t])
    lb_h.simulate_processing(PROCESSING_RATE)
    if max(lb_h.region_loads.values()) > THRESHOLD:
        hyster_count += 1
    hyster_cumsum.append(hyster_count)
    
    target_g = lb_g.get_target_region(INGRESS)
    lb_g.update_load(target_g, traffic[t])
    lb_g.simulate_processing(PROCESSING_RATE)
    if max(lb_g.region_loads.values()) > THRESHOLD:
        greedy_count += 1
    greedy_cumsum.append(greedy_count)

ax.plot(hyster_cumsum, label='α=0.7', color='green', linewidth=2)
ax.plot(greedy_cumsum, label='α=1.0', color='red', linewidth=2)
ax.set_xlabel('Time Step')
ax.set_ylabel('Cumulative Violations')
ax.set_title('Violation Accumulation Over Time')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 3: Oscillation vs Redirect counts
ax = axes[1, 0]
metrics = ['Violations', 'Redirects', 'Oscillations']
hyster_vals = [violations_hysteresis, redirects_hysteresis, oscillations_hysteresis]
greedy_vals = [violations_greedy, redirects_greedy, oscillations_greedy]

x = np.arange(len(metrics))
width = 0.35

bars1 = ax.bar(x - width/2, hyster_vals, width, label='α=0.7', color='green', alpha=0.7, edgecolor='black')
bars2 = ax.bar(x + width/2, greedy_vals, width, label='α=1.0', color='red', alpha=0.7, edgecolor='black')

ax.set_ylabel('Count')
ax.set_title('Key Metrics Comparison')
ax.set_xticks(x)
ax.set_xticklabels(metrics)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# Add value labels
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=9)

# Plot 4: Stability metrics
ax = axes[1, 1]
stability_categories = ['Entropy\n(routing)', 'Flap Events\n(changes)', 'Oscillations\n(A→B→A)']
hyster_stab = [entropy_hysteresis, consecutive_redirects_hysteresis / 50, oscillations_hysteresis]
greedy_stab = [entropy_greedy, consecutive_redirects_greedy / 50, oscillations_greedy]

x = np.arange(len(stability_categories))
bars1 = ax.bar(x - width/2, hyster_stab, width, label='α=0.7', color='green', alpha=0.7, edgecolor='black')
bars2 = ax.bar(x + width/2, greedy_stab, width, label='α=1.0', color='red', alpha=0.7, edgecolor='black')

ax.set_ylabel('Metric Value')
ax.set_title('Routing Stability Indicators')
ax.set_xticks(x)
ax.set_xticklabels(stability_categories, fontsize=9)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
output_path = 'enhanced_flapping_scenario.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"\n✓ Visualization saved to: {output_path}")

print("\n" + "=" * 90)
print("KEY FINDINGS")
print("=" * 90)
print(f"""
In this tight-threshold environment:

1. STABILITY:
   Hysteresis (α=0.7) preferred routing sticky (entropy: {entropy_hysteresis:.3f})
   Greedy (α=1.0) constantly searches for optimal (entropy: {entropy_greedy:.3f})

2. OSCILLATION PATTERN:
   Even with identical traffic, the algorithms discover different routing strategies:
   - Hysteresis finds a stable (but not optimal) routing pattern
   - Greedy tries to optimize but may cause excessive switching

3. REAL-WORLD LESSON:
   Close decisions around threshold boundaries create the perfect storm for oscillation.
   Hysteresis prevents this by saying: "If current region is close enough, stay put."
   This stability is often MORE valuable than theoretical optimal routing.
""")

print("=" * 90)
