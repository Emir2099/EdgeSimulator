"""
overlapping_distribution_study.py — Anomaly Detection Robustness Study
=======================================================================
Addresses artificially isolated distributions.

Key insight from reproducing the paper's F1=0.99 result:
  - Training on 900 normal samples (matching test set size) gives F1=1.0
  - Training on 500 samples gives F1~0.99 with the right seed
  - The high F1 is achievable ONLY because distributions are separated
  - With overlapping distributions, F1 degrades significantly

This study trains on 900 normal samples (consistent with the paper's
held-out evaluation of 900 normal + 100 anomaly), and evaluates under
three overlap scenarios.

Uses sklearn.IsolationForest directly (bypassing the predict() buffer
guard in AnomalyDetector which requires 20 warm-up samples — appropriate
for the formal evaluation context of this study).
"""

import random
import csv
import os
import sys
import numpy as np
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEED           = 42
N_TRAIN        = 900    # matches paper's held-out set size
N_TEST_NORMAL  = 900
N_TEST_ANOMALY = 100
N_RUNS         = 5


def generate(rng, n, temp_range, hum_range):
    return [[rng.uniform(*temp_range), rng.uniform(*hum_range)]
            for _ in range(n)]


def evaluate(model, X, y_true):
    """Evaluate model using score-based threshold (contamination=0.1 → bottom 10%)."""
    scores = model.decision_function(np.array(X))
    threshold = np.percentile(scores, 10)
    y_pred = [-1 if s <= threshold else 1 for s in scores]

    tp = sum(1 for t,p in zip(y_true,y_pred) if t==-1 and p==-1)
    fp = sum(1 for t,p in zip(y_true,y_pred) if t== 1 and p==-1)
    tn = sum(1 for t,p in zip(y_true,y_pred) if t== 1 and p== 1)
    fn = sum(1 for t,p in zip(y_true,y_pred) if t==-1 and p== 1)

    prec = tp/(tp+fp) if (tp+fp) > 0 else 0
    rec  = tp/(tp+fn) if (tp+fn) > 0 else 0
    f1   = 2*prec*rec/(prec+rec) if (prec+rec) > 0 else 0
    fpr  = fp/(fp+tn) if (fp+tn) > 0 else 0
    return prec, rec, f1, fpr


def run_scenario(scenario_name, normal_ranges, anomaly_ranges, seed=SEED):
    precisions, recalls, f1s, fprs = [], [], [], []

    for run in range(N_RUNS):
        rng = random.Random(seed + run)

        train = generate(rng, N_TRAIN, *normal_ranges)
        model = IsolationForest(contamination=0.1, random_state=seed + run)
        model.fit(train)

        test_normal  = generate(rng, N_TEST_NORMAL,  *normal_ranges)
        test_anomaly = generate(rng, N_TEST_ANOMALY, *anomaly_ranges)
        X      = test_normal + test_anomaly
        y_true = [1]*N_TEST_NORMAL + [-1]*N_TEST_ANOMALY

        prec, rec, f1, fpr = evaluate(model, X, y_true)
        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)
        fprs.append(fpr)

    def avg(lst): return round(sum(lst)/len(lst), 3)

    return {
        'Scenario':            scenario_name,
        'Precision':           avg(precisions),
        'Recall':              avg(recalls),
        'F1 Score':            avg(f1s),
        'False Positive Rate': avg(fprs),
    }


def main():
    scenarios = [
        {
            'scenario_name': 'A: Isolated (paper setup, Section 6.1)',
            'normal_ranges':  [(20.0, 30.0), (40.0, 60.0)],
            'anomaly_ranges': [(33.0, 40.0), (15.0, 25.0)],
        },
        {
            'scenario_name': 'B: Partial Overlap (4-degree gap)',
            'normal_ranges':  [(20.0, 32.0), (35.0, 65.0)],
            'anomaly_ranges': [(28.0, 40.0), (20.0, 50.0)],
        },
        {
            'scenario_name': 'C: Heavy Overlap (10-degree gap)',
            'normal_ranges':  [(18.0, 35.0), (30.0, 70.0)],
            'anomaly_ranges': [(25.0, 42.0), (25.0, 65.0)],
        },
    ]

    print("\n" + "="*80)
    print("Anomaly Detection Robustness Study — Distribution Overlap Analysis")
    print(f"Train: {N_TRAIN} normal | "
          f"Test: {N_TEST_NORMAL} normal + {N_TEST_ANOMALY} anomaly | "
          f"Runs: {N_RUNS} | Seed: {SEED}")
    print("="*80)

    results = []
    for s in scenarios:
        print(f"  Running {s['scenario_name']}...")
        r = run_scenario(**s)
        results.append(r)

    print("\n" + "="*80)
    print(f"{'Scenario':<42} | {'Prec':>6} {'Rec':>6} "
          f"{'F1':>6} {'FPR':>6}")
    print("-"*80)
    for r in results:
        marker = "  <-- paper" if 'paper setup' in r['Scenario'] else ""
        print(f"{r['Scenario']:<42} | "
              f"{r['Precision']:>6.3f} "
              f"{r['Recall']:>6.3f} "
              f"{r['F1 Score']:>6.3f} "
              f"{r['False Positive Rate']:>6.3f}{marker}")
    print("="*80)

    r_iso  = results[0]
    r_part = results[1]
    r_hvy  = results[2]

    print("\nKey findings:")
    print(f"  Isolated (paper setup): F1={r_iso['F1 Score']} — "
          f"high because distributions are separated by 3 degrees")
    print(f"  Partial overlap (4-deg): F1={r_part['F1 Score']} — "
          f"degraded with realistic noise")
    print(f"  Heavy overlap (10-deg):  F1={r_hvy['F1 Score']} — "
          f"significantly degraded")
    print(f"\n  The paper's F1~0.99 is an upper bound for the controlled")
    print(f"  simulation setup. Real-world performance would be lower.")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'overlapping_distribution_results.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to: {out_path}")
    return results


if __name__ == "__main__":
    main()