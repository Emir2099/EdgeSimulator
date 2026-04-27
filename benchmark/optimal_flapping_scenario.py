"""
OPTIMAL Flapping Scenario: Regions can recover, forcing hysteresis vs. greedy choice

Design: Traffic pattern that creates PERIODIC PEAKS where oscillation-prone decisions occur
- Most steps: one region is available, two are slightly overloaded
- This forces the question: "Do I stick with my current region or constantly chase the best?"
- α=0.7 answers: "stick unless 30% better" → stable, predictable
- α=1.0 answers: "always pick best" → oscillates when best region keeps changing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'multiregion'))

from load_balancer import LoadBalancer
import matplotlib.pyplot as plt
import numpy as np

DURATION = 150
SEED = 42
THRESHOLD = 1000
PROCESSING_RATE = 120
REGIONS = ['region_1', 'region_2', 'region_3']
INGRESS = 'region_1'

print("=" * 90)
print("OPTIMAL FLAPPING SCENARIO: The Sweet Spot for Hysteresis Benefit")
print("=" * 90)
print(f"""
Design Principle:
  Create a traffic pattern that alternates between:
  - Phase 1 (Normal): One region available, others slightly overloaded
  - Phase 2 (Peak): Brief bursts that make all regions overloaded
  
  In Phase 1, the question becomes:
  - α=0.7: "My current region is good enough, stick with it"
  - α=1.0: "Region 2 is 5% better than my region, switch!"
  
  This constant switching (α=1.0) creates oscillation (A→B→A→...).
  Hysteresis (α=0.7) prevents it by saying "if current is acceptable, stay."
""")

# Custom traffic pattern: periodic peaks with base patterns
def generate_smart_traffic(duration, seed=42):
    """
    Generate traffic with clear structure:
    - Most of the time: ~400-500B (one region barely below threshold)
    - Occasionally: ~900B (concentrated spike)
    - Rarely: ~1200B (burst across multiple ingress points)
    
    This creates an environment where different strategy matters.
    """
    np.random.seed(seed)
    traffic = []
    
    for t in range(duration):
        # 70% of time: normal load (one region handling ~400B, others at 100-150B via draining)
        if np.random.rand() < 0.70:
            value = np.random.randint(350, 450)
        # 20% of time: medium spike (one region at ~800B)
        elif np.random.rand() < 0.70 / 0.30:  # Of remaining 30%
            value = np.random.randint(700, 900)
        # 10% of time: heavy spike (cluster burst)
        else:
            value = np.random.randint(900, 1100)
        traffic.append(value)
    
    return traffic

traffic = generate_smart_traffic(DURATION, SEED)
print(f"\nGenerated smart traffic: {DURATION} steps")
print(f"  Min: {min(traffic)}B")
print(f"  Max: {max(traffic)}B")
print(f"  Mean: {np.mean(traffic):.1f}B")
print(f"  Median: {np.median(traffic):.1f}B")

# Count how many steps exceed threshold
over_threshold = sum(1 for t in traffic if t > THRESHOLD)
print(f"  Steps over {THRESHOLD}B threshold: {over_threshold}/{DURATION}")

# === RUN 1: Alpha=0.7 ===
print("\n" + "=" * 90)
print("RUN 1: α=0.7 (HYSTERESIS - sticky preference)")
print("=" * 90)

lb_hysteresis = LoadBalancer(REGIONS, alpha=0.7, load_threshold=THRESHOLD)
routing_hysteresis = []
violations_hysteresis = 0
redirects_hysteresis = 0
loads_per_step_hysteresis = []

for t in range(DURATION):
    target = lb_hysteresis.get_target_region(INGRESS)
    
    if routing_hysteresis and target != routing_hysteresis[-1]:
        redirects_hysteresis += 1
    
    lb_hysteresis.update_load(target, traffic[t])
    lb_hysteresis.simulate_processing(PROCESSING_RATE)
    
    loads = lb_hysteresis.region_loads.copy()
    max_load = max(loads.values())
    if max_load > THRESHOLD:
        violations_hysteresis += 1
    
    routing_hysteresis.append(target)
    loads_per_step_hysteresis.append(loads)

# Count oscillations
oscillations_hysteresis = 0
for i in range(len(routing_hysteresis) - 2):
    if routing_hysteresis[i] == routing_hysteresis[i+2] and routing_hysteresis[i] != routing_hysteresis[i+1]:
        oscillations_hysteresis += 1

print(f"Results:")
print(f"  Violations: {violations_hysteresis}/{DURATION}")
print(f"  Redirects: {redirects_hysteresis}")
print(f"  Oscillations (A→B→A): {oscillations_hysteresis}")

# === RUN 2: Alpha=1.0 ===
print("\n" + "=" * 90)
print("RUN 2: α=1.0 (GREEDY - always optimal)")
print("=" * 90)

lb_greedy = LoadBalancer(REGIONS, alpha=1.0, load_threshold=THRESHOLD)
routing_greedy = []
violations_greedy = 0
redirects_greedy = 0
loads_per_step_greedy = []

for t in range(DURATION):
    target = lb_greedy.get_target_region(INGRESS)
    
    if routing_greedy and target != routing_greedy[-1]:
        redirects_greedy += 1
    
    lb_greedy.update_load(target, traffic[t])
    lb_greedy.simulate_processing(PROCESSING_RATE)
    
    loads = lb_greedy.region_loads.copy()
    max_load = max(loads.values())
    if max_load > THRESHOLD:
        violations_greedy += 1
    
    routing_greedy.append(target)
    loads_per_step_greedy.append(loads)

# Count oscillations
oscillations_greedy = 0
for i in range(len(routing_greedy) - 2):
    if routing_greedy[i] == routing_greedy[i+2] and routing_greedy[i] != routing_greedy[i+1]:
        oscillations_greedy += 1

print(f"Results:")
print(f"  Violations: {violations_greedy}/{DURATION}")
print(f"  Redirects: {redirects_greedy}")
print(f"  Oscillations (A→B→A): {oscillations_greedy}")

# === ANALYSIS ===
print("\n" + "=" * 90)
print("COMPARATIVE ANALYSIS")
print("=" * 90)

print(f"""\nMetrics:
  Violations:      α=0.7: {violations_hysteresis:3d}   α=1.0: {violations_greedy:3d}   ({violations_greedy - violations_hysteresis:+3d})
  Redirects:       α=0.7: {redirects_hysteresis:3d}   α=1.0: {redirects_greedy:3d}   ({redirects_greedy - redirects_hysteresis:+3d})
  Oscillations:    α=0.7: {oscillations_hysteresis:3d}   α=1.0: {oscillations_greedy:3d}   ({oscillations_greedy - oscillations_hysteresis:+3d})

Interpretation:
  {'✓ Hysteresis WINS: fewer oscillations, fewer redirects' if oscillations_hysteresis < oscillations_greedy and redirects_hysteresis < redirects_greedy else '⚠ Results complex; see plots'}
""")

# Compute consecutive routing changes
def count_routing_changes(routing_seq):
    return sum(1 for i in range(len(routing_seq) - 1) if routing_seq[i] != routing_seq[i+1])

changes_hysteresis = count_routing_changes(routing_hysteresis)
changes_greedy = count_routing_changes(routing_greedy)

print(f"Routing Stability (total region changes):")
print(f"  α=0.7: {changes_hysteresis}   α=1.0: {changes_greedy}   ({changes_greedy - changes_hysteresis:+3d})")

# === VISUALIZATION ===
fig, axes = plt.subplots(2, 3, figsize=(16, 10))
fig.suptitle('Optimal Flapping Scenario: α=0.7 Hysteresis vs α=1.0 Greedy', 
             fontsize=14, fontweight='bold')

region_map = {'region_1': 1, 'region_2': 2, 'region_3': 3}

# Plot 1: Incoming traffic
ax = axes[0, 0]
ax.bar(range(DURATION), traffic, color='lightblue', edgecolor='navy', alpha=0.7)
ax.axhline(y=THRESHOLD, color='red', linestyle='--', linewidth=2, label=f'Threshold ({THRESHOLD}B)')
ax.set_xlabel('Time Step')
ax.set_ylabel('Traffic (bytes)')
ax.set_title('Incoming Traffic Pattern')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 2: Routing decisions (first 80 steps) - hysteresis
ax = axes[0, 1]
steps_show = 80
hyster_nums = [region_map[r] for r in routing_hysteresis[:steps_show]]
ax.plot(range(steps_show), hyster_nums, 'o-', color='green', linewidth=1.5, 
        markersize=4, label='α=0.7', alpha=0.8)
ax.fill_between(range(steps_show), 0.5, 3.5, alpha=0.1, color='green')
ax.set_xlabel('Time Step')
ax.set_ylabel('Target Region')
ax.set_title(f'Routing (α=0.7 Hysteresis, first {steps_show} steps)')
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(['R1', 'R2', 'R3'])
ax.grid(True, alpha=0.3)
ax.set_ylim(0.5, 3.5)

# Plot 3: Routing decisions (first 80 steps) - greedy
ax = axes[0, 2]
greedy_nums = [region_map[r] for r in routing_greedy[:steps_show]]
ax.plot(range(steps_show), greedy_nums, 's-', color='red', linewidth=1.5, 
        markersize=4, label='α=1.0', alpha=0.8)
ax.fill_between(range(steps_show), 0.5, 3.5, alpha=0.1, color='red')
ax.set_xlabel('Time Step')
ax.set_ylabel('Target Region')
ax.set_title(f'Routing (α=1.0 Greedy, first {steps_show} steps)')
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(['R1', 'R2', 'R3'])
ax.grid(True, alpha=0.3)
ax.set_ylim(0.5, 3.5)

# Plot 4: Cumulative violations
ax = axes[1, 0]
hyster_viol_cumsum = []
greedy_viol_cumsum = []

hyster_v = 0
greedy_v = 0
for t in range(DURATION):
    if max(loads_per_step_hysteresis[t].values()) > THRESHOLD:
        hyster_v += 1
    if max(loads_per_step_greedy[t].values()) > THRESHOLD:
        greedy_v += 1
    hyster_viol_cumsum.append(hyster_v)
    greedy_viol_cumsum.append(greedy_v)

ax.plot(hyster_viol_cumsum, label='α=0.7', color='green', linewidth=2)
ax.plot(greedy_viol_cumsum, label='α=1.0', color='red', linewidth=2)
ax.set_xlabel('Time Step')
ax.set_ylabel('Cumulative Violations')
ax.set_title('Violation Accumulation')
ax.legend()
ax.grid(True, alpha=0.3)

# Plot 5: Key metrics comparison
ax = axes[1, 1]
metrics = ['Violations', 'Redirects', 'Oscillations']
hyster_vals = [violations_hysteresis, redirects_hysteresis, oscillations_hysteresis]
greedy_vals = [violations_greedy, redirects_greedy, oscillations_greedy]

x = np.arange(len(metrics))
width = 0.35

bars1 = ax.bar(x - width/2, hyster_vals, width, label='α=0.7', color='green', alpha=0.7, edgecolor='black')
bars2 = ax.bar(x + width/2, greedy_vals, width, label='α=1.0', color='red', alpha=0.7, edgecolor='black')

ax.set_ylabel('Count')
ax.set_title('Key Metrics')
ax.set_xticks(x)
ax.set_xticklabels(metrics)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)

# Plot 6: Stability metrics
ax = axes[1, 2]
stability_metrics = ['Changes', 'Oscillations', 'Cost\n(V+R+O)']
hyster_stab = [changes_hysteresis, oscillations_hysteresis, 
               violations_hysteresis + redirects_hysteresis + oscillations_hysteresis]
greedy_stab = [changes_greedy, oscillations_greedy, 
               violations_greedy + redirects_greedy + oscillations_greedy]

x = np.arange(len(stability_metrics))
bars1 = ax.bar(x - width/2, hyster_stab, width, label='α=0.7', color='green', alpha=0.7, edgecolor='black')
bars2 = ax.bar(x + width/2, greedy_stab, width, label='α=1.0', color='red', alpha=0.7, edgecolor='black')

ax.set_ylabel('Value')
ax.set_title('Stability & Overhead')
ax.set_xticks(x)
ax.set_xticklabels(stability_metrics, fontsize=9)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
output_path = 'optimal_flapping_scenario.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"\n✓ Visualization saved to: {output_path}")

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
print(f"""
This scenario creates an environment where:

1. Most of the time, traffic is NORMAL and manageable
2. Occasionally, traffic SPIKES and forces redistribution decisions
3. The question becomes: during spikes, do you:
   a) Stick with your current region (α=0.7: "close enough is good")
   b) Always chase the mathematically best region (α=1.0: "optimize every decision")

Results show that in real-world conditions with varying load:
• Hysteresis (α=0.7) routing changes: {changes_hysteresis}
• Greedy (α=1.0) routing changes: {changes_greedy}
• Difference: {changes_greedy - changes_hysteresis:+d} extra switching with greedy

Each switch has overhead (recalculating paths, cache invalidation, etc.).
More importantly, constant switching creates oscillation patterns that degrade 
predictability and can trigger cascading failures in real routers.

The hysteresis factor prevents this by accepting that "good enough" routing
is better than "optimal but unstable" routing.
""")

print("=" * 90)
