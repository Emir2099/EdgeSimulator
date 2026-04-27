"""
Aligned parameters (from multiregion/ablation_study.py):
- SEED = 42
- BURST_PROB = 0.15
- BURST_EXTRA = (800, 1100)

This script keeps the Table 6 strategy comparison format:
Round-Robin vs Least Connections vs S-Edge over 100 steps.
"""

import sys
import os
import matplotlib.pyplot as plt

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
multiregion_dir = os.path.join(parent_dir, 'multiregion')
for p in (parent_dir, multiregion_dir):
    if p not in sys.path:
        sys.path.append(p)

from lb_shared_engine import (
    REGIONS,
    THRESHOLD,
    PROCESSING_RATE,
    SEED,
    BURST_PROB,
    BURST_EXTRA,
    BASE_LOAD,
    DURATION,
    generate_traffic_sequence,
    run_round_robin,
    run_least_connections,
    run_sedge_lb_only,
)

traffic = generate_traffic_sequence(DURATION, SEED, BURST_PROB, BURST_EXTRA, BASE_LOAD)


def main():
    print("Running Table 6 (Table 8 comparable workload)...")
    print(f"SEED={SEED}, BURST_PROB={BURST_PROB}, BURST_EXTRA={BURST_EXTRA}, BASE_LOAD={BASE_LOAD}")

    rr = run_round_robin(traffic, REGIONS, THRESHOLD, PROCESSING_RATE)
    lc = run_least_connections(traffic, REGIONS, THRESHOLD, PROCESSING_RATE)
    se = run_sedge_lb_only(traffic, REGIONS, THRESHOLD, PROCESSING_RATE, alpha=0.7, ingress=REGIONS[0])

    rr_v, rr_f, rr_cpu = rr['violations'], rr['flaps'], rr['mean_cpu']
    lc_v, lc_f, lc_cpu = lc['violations'], lc['flaps'], lc['mean_cpu']
    se_v, se_f, se_cpu = se['violations'], se['flaps'], se['mean_cpu']

    header = f"{'Metric':<28} {'Round-Robin':>14} {'Least Conn.':>14} {'S-Edge':>14}"
    sep = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)
    print(f"{'Threshold violations':<28} {rr_v:>10}/100 {lc_v:>10}/100 {se_v:>10}/100")
    print(f"{'Load-flapping events':<28} {'N/A':>14} {lc_f:>14} {se_f:>14}")
    print(f"{'Mean CPU utilization':<28} {rr_cpu:>13.1f}% {lc_cpu:>13.1f}% {se_cpu:>13.1f}%")
    print(sep)

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis('off')
    col_labels = ['Metric', 'Round-Robin', 'Least Connections', 'S-Edge']
    table_data = [
        ['Threshold violations', f'{rr_v}/100', f'{lc_v}/100', f'{se_v}/100'],
        ['Load-flapping events', 'N/A', str(lc_f), str(se_f)],
        ['Mean CPU utilization', f'~{rr_cpu:.1f}%', f'~{lc_cpu:.1f}%', f'~{se_cpu:.1f}%'],
    ]

    tbl = ax.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.2, 1.6)

    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor('#4472C4')
        cell.set_text_props(color='white', fontweight='bold')

    for i in range(1, len(table_data) + 1):
        for j in range(len(col_labels)):
            cell = tbl[i, j]
            cell.set_facecolor('#D9E2F3' if i % 2 == 0 else 'white')

    ax.set_title('Table 6 (Table 8 Comparable Workload)', fontsize=13, fontweight='bold', pad=20)
    plt.tight_layout()

    out_path = os.path.join(current_dir, 'load_balancing_table_comparable.png')
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved: {out_path}")


if __name__ == '__main__':
    main()
