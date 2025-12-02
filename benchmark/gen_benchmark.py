import matplotlib.pyplot as plt
import random
import sys
import os

# --- PATH SETUP ---
# This adds the parent directory to Python's path so it can find load_balancer.py
# Use this if gen_benchmark.py is in a subfolder like 'tests/' or 'experiments/'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now we can import your fixed class
try:
    from load_balancer import LoadBalancer
except ImportError:
    # Fallback if the file structure is different (e.g. inside a 'multiregion' package)
    from multiregion.load_balancer import LoadBalancer

# --- CONFIGURATION ---
REGIONS = ['region_1', 'region_2', 'region_3']
DURATION = 100         # Time steps
THRESHOLD = 1000       # Matches your load_balancer.py threshold
PROCESSING_RATE = 20   # How fast the server clears data per step

# --- 1. SETUP BASELINE (ROUND ROBIN) ---
baseline_loads = {r: 0 for r in REGIONS}
baseline_history = {r: [] for r in REGIONS}
baseline_index = 0

# --- 2. SETUP PROPOSED (YOUR CODE) ---
smart_lb = LoadBalancer(REGIONS)
# We will disable the print statement inside redistribution if needed to keep console clean
smart_history = {r: [] for r in REGIONS}

print("Running Benchmark: Your Code vs. Round Robin...")

for t in range(DURATION):
    # Generate Traffic (Bursty!)
    # 20% chance of a huge file (video), 80% chance of small file (sensor)
    if random.random() < 0.2:
        traffic = random.randint(300, 600)
    else:
        traffic = random.randint(10, 50)

    # -----------------------------
    # A. Run Baseline (Round Robin)
    # -----------------------------
    target = REGIONS[baseline_index]
    baseline_loads[target] += traffic
    baseline_index = (baseline_index + 1) % len(REGIONS)
    
    # Simulate Processing (Baseline)
    for r in REGIONS:
        baseline_loads[r] = max(0, baseline_loads[r] - PROCESSING_RATE)
        baseline_history[r].append(baseline_loads[r])

    # -----------------------------
    # B. Run Your S-Edge Code
    # -----------------------------
    # Assume 'region_1' is the default ingress
    ingress_region = REGIONS[t % 3] 
    
    # 1. ADD LOAD (Uses your updated logic with redistribution)
    smart_lb.update_load(ingress_region, traffic)
    
    # 2. PROCESS LOAD (Uses the new method we just added)
    smart_lb.simulate_processing(PROCESSING_RATE)

    # Record history for plotting
    for r in REGIONS:
        with smart_lb.lock: 
            smart_history[r].append(smart_lb.region_loads[r])

# --- 3. PLOTTING ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

# Plot Baseline
for r in REGIONS:
    ax1.plot(baseline_history[r], label=r, linewidth=2, alpha=0.7)
ax1.axhline(y=THRESHOLD, color='r', linestyle='--', linewidth=2, label='Threshold (1000)')
ax1.set_title("Baseline (Round Robin)", fontsize=14, fontweight='bold')
ax1.set_xlabel("Time Steps")
ax1.set_ylabel("Queue Load")
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper right')

# Plot Your Code
for r in REGIONS:
    ax2.plot(smart_history[r], label=r, linewidth=2, alpha=0.7)
ax2.axhline(y=THRESHOLD, color='r', linestyle='--', linewidth=2, label='Threshold (1000)')
ax2.set_title("S-Edge (Proposed)", fontsize=14, fontweight='bold')
ax2.set_xlabel("Time Steps")
ax2.grid(True, alpha=0.3)
ax2.legend(loc='upper right')

plt.suptitle("Benchmark: Efficiency of S-Edge Load Balancer", fontsize=16)
plt.tight_layout()
plt.savefig('load_balancing_comparison.png', dpi=300)
print("Graph generated: load_balancing_comparison.png")
# plt.show() # Uncomment if you want to see it pop up