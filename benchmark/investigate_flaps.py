"""
Investigate S-Edge and LC oscillation events side-by-side.
For each time-step, log: traffic, target chosen, loads, and whether an oscillation occurred.
"""

import random
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')
for p in (parent_dir, multiregion_dir):
    if p not in sys.path:
        sys.path.append(p)

from load_balancer import LoadBalancer

# Same config as gen_lb_table.py
REGIONS         = ['region_1', 'region_2', 'region_3']
DURATION        = 100
THRESHOLD       = 1000
PROCESSING_RATE = 120
SEED            = 42

def generate_traffic_sequence(n, seed):
    rng = random.Random(seed)
    seq = []
    for _ in range(n):
        r = rng.random()
        if r < 0.10:
            seq.append(rng.randint(800, 1200))
        elif r < 0.30:
            seq.append(rng.randint(300, 600))
        else:
            seq.append(rng.randint(10, 80))
    return seq

traffic = generate_traffic_sequence(DURATION, SEED)

# -------------------------------------------------------
# Least Connections — full trace
# -------------------------------------------------------
lc_loads = {r: 0 for r in REGIONS}
lc_history = []
lc_flap_steps = []

for t in range(DURATION):
    target = min(lc_loads, key=lc_loads.get)
    lc_loads[target] += traffic[t]
    for r in REGIONS:
        lc_loads[r] = max(0, lc_loads[r] - PROCESSING_RATE)

    lc_history.append(target)
    if len(lc_history) >= 3:
        if lc_history[-1] == lc_history[-3] and lc_history[-1] != lc_history[-2]:
            lc_flap_steps.append(t)

# -------------------------------------------------------
# S-Edge — full trace
# -------------------------------------------------------
lb = LoadBalancer(REGIONS)
se_history = []
se_flap_steps = []
se_trace = []  # detailed per-step info

for t in range(DURATION):
    ingress = REGIONS[0]
    current_load = lb.region_loads[ingress]
    optimal = lb.get_optimal_region()
    opt_load = lb.region_loads[optimal]

    redirected = False
    if optimal != ingress and opt_load < current_load * 0.7:
        target = optimal
        redirected = True
    else:
        target = ingress

    loads_before = dict(lb.region_loads)
    lb.update_load(target, traffic[t])
    lb.simulate_processing(PROCESSING_RATE)
    loads_after = dict(lb.region_loads)

    se_history.append(target)
    is_flap = False
    if len(se_history) >= 3:
        if se_history[-1] == se_history[-3] and se_history[-1] != se_history[-2]:
            se_flap_steps.append(t)
            is_flap = True

    se_trace.append({
        't': t,
        'traffic': traffic[t],
        'ingress': ingress,
        'optimal': optimal,
        'target': target,
        'redirected': redirected,
        'hysteresis_check': f"{opt_load} < {current_load * 0.7:.0f} (0.7 * {current_load})",
        'loads_before': loads_before,
        'loads_after': loads_after,
        'is_flap': is_flap,
    })

# -------------------------------------------------------
# Report
# -------------------------------------------------------
print("=" * 90)
print("S-EDGE OSCILLATION EVENTS (A→B→A pattern)")
print("=" * 90)
for step in se_flap_steps:
    tr = se_trace[step]
    prev2 = se_trace[step - 2]
    prev1 = se_trace[step - 1]
    print(f"\n--- Oscillation at t={step} (pattern: {se_history[step-2]} → {se_history[step-1]} → {se_history[step]}) ---")
    for label, s in [("t-2", prev2), ("t-1", prev1), ("t  ", tr)]:
        print(f"  [{label}] traffic={s['traffic']:>5}  target={s['target']}  "
              f"redirected={s['redirected']}  "
              f"loads_before={s['loads_before']}  "
              f"loads_after={s['loads_after']}")
        if label == "t  ":
            print(f"         hysteresis: {s['hysteresis_check']}")

    # Check: what did LC do at the same steps?
    print(f"  [LC at t-2..t] targets: {lc_history[step-2]} → {lc_history[step-1]} → {lc_history[step]}")
    lc_also_flapped = step in lc_flap_steps
    print(f"  LC also oscillated here? {'YES' if lc_also_flapped else 'NO'}")

print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
print(f"S-Edge oscillations: {len(se_flap_steps)} at steps {se_flap_steps}")
print(f"LC oscillations:     {len(lc_flap_steps)} at steps {lc_flap_steps}")

# Check overlap
overlap = set(se_flap_steps) & set(lc_flap_steps)
se_only = set(se_flap_steps) - set(lc_flap_steps)
lc_only = set(lc_flap_steps) - set(se_flap_steps)
print(f"\nBoth oscillated at same step:   {sorted(overlap) if overlap else 'none'}")
print(f"S-Edge only oscillated at:      {sorted(se_only) if se_only else 'none'}")
print(f"LC only oscillated at:          {sorted(lc_only) if lc_only else 'none'}")

# Traffic classification at S-Edge flap steps
print(f"\nTraffic at S-Edge flap steps:")
for step in se_flap_steps:
    t_val = traffic[step]
    kind = "EXTREME" if t_val >= 800 else ("MODERATE" if t_val >= 300 else "LIGHT")
    t_prev = traffic[step-1]
    kind_prev = "EXTREME" if t_prev >= 800 else ("MODERATE" if t_prev >= 300 else "LIGHT")
    print(f"  t={step}: traffic={t_val} ({kind}), t-1 traffic={t_prev} ({kind_prev})")
