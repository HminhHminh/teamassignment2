#!/usr/bin/env python3
"""Section 6.1 trade-off experiment: synchronization frequency vs execution time.

Runs Approach 3 with a shared counter updated every k iterations, plus two
reference points at the same (N, T): Approach 2 (local accumulation) and
Approach 3 (mutex on every hit). Writes raw runs, a summary table, and a plot.

Usage:
    python run_sync_frequency.py [--exe PATH] [--points N] [--threads T] [--runs R]
"""

import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH_DIR = os.path.join(HERE, "..", "3_graphs")
os.makedirs(GRAPH_DIR, exist_ok=True)

EXE_CANDIDATES = [
    os.environ.get("MONTE_CARLO_EXE", ""),
    os.path.join(HERE, "monte_carlo.exe"),
    os.path.join(HERE, "..", "1_source_code", "monte_carlo.exe"),
    os.path.join(HERE, "..", "..", "teamassignment2", "monte_carlo.exe"),
    os.path.join(HERE, "..", "1_source_code", "monte_carlo"),
    os.path.join(HERE, "..", "..", "teamassignment2", "monte_carlo"),
]


def find_exe(override):
    if override:
        if not os.path.isfile(override):
            raise SystemExit(f"Executable not found: {override}")
        return os.path.abspath(override)
    for path in EXE_CANDIDATES:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    raise SystemExit("monte_carlo executable not found; build it first or pass --exe PATH")


def run(exe, approach, threads, points, runs, k=1000):
    cmd = [exe, "-a", str(approach), "-t", str(threads), "-n", str(points),
           "-k", str(k), "-s", "123456789", "-r", str(runs), "--csv"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{proc.stderr}")
    rows = []
    for line in proc.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 7:
            rows.append({"approach": parts[0], "threads": int(parts[1]),
                         "points": int(parts[2]), "k": int(parts[3]),
                         "run": int(parts[4]), "time": float(parts[5]),
                         "pi": float(parts[6])})
    if len(rows) != runs:
        raise RuntimeError(f"expected {runs} rows, got {len(rows)}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="")
    ap.add_argument("--points", type=int, default=30_000_000)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    exe = find_exe(args.exe)
    ks = [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000]

    print(f"exe={exe}\nN={args.points:,} T={args.threads} runs={args.runs}")

    raw = []
    baseline = run(exe, 1, 1, args.points, args.runs)
    t_single = statistics.mean(r["time"] for r in baseline)
    raw.extend(baseline)
    print(f"Approach 1 baseline: {t_single:.6f} s")

    local = run(exe, 2, args.threads, args.points, args.runs)
    t_local = statistics.mean(r["time"] for r in local)
    raw.extend(local)
    print(f"Approach 2 local:    {t_local:.6f} s")

    per_hit = run(exe, 3, args.threads, args.points, args.runs)
    t_per_hit = statistics.mean(r["time"] for r in per_hit)
    raw.extend(per_hit)
    print(f"Approach 3 per-hit:  {t_per_hit:.6f} s")

    summary = []
    for k in ks:
        rows = run(exe, "batch", args.threads, args.points, args.runs, k=k)
        raw.extend(rows)
        times = [r["time"] for r in rows]
        mean_t = statistics.mean(times)
        std_t = statistics.stdev(times) if len(times) > 1 else 0.0
        item = {
            "k": k,
            "mean_time_s": mean_t,
            "std_time_s": std_t,
            "speedup_vs_single": t_single / mean_t,
            "throughput_mpts": (args.points / mean_t) / 1e6,
            "pi_mean": statistics.mean(r["pi"] for r in rows),
        }
        summary.append(item)
        print(f"k={k:>8,}  {mean_t:.6f} +/- {std_t:.6f} s  "
              f"speedup {item['speedup_vs_single']:.2f}x  pi {item['pi_mean']:.6f}")

    with open(os.path.join(HERE, "sync_frequency_runs.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["approach", "threads", "points", "k", "run", "time", "pi"])
        w.writeheader()
        w.writerows(raw)

    with open(os.path.join(HERE, "sync_frequency_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["k", "mean_time_s", "std_time_s",
                                          "speedup_vs_single", "throughput_mpts", "pi_mean"])
        w.writeheader()
        w.writerows(summary)

    metadata = {
        "experiment": "Section 6.1 synchronization frequency trade-off",
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpus": os.cpu_count(),
        },
        "points": args.points,
        "threads": args.threads,
        "runs_per_config": args.runs,
        "single_thread_baseline_s": t_single,
        "approach2_local_s": t_local,
        "approach3_per_hit_s": t_per_hit,
        "k_values": ks,
    }
    with open(os.path.join(HERE, "sync_frequency_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    plot(summary, t_single, t_local, t_per_hit, args.points, args.threads)


def plot(summary, t_single, t_local, t_per_hit, points, threads):
    ks = [x["k"] for x in summary]
    means = [x["mean_time_s"] for x in summary]
    stds = [x["std_time_s"] for x in summary]
    speedups = [x["speedup_vs_single"] for x in summary]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.errorbar(ks, means, yerr=stds, fmt="-o", color="#9467bd", ecolor="#c5b0d5",
                 elinewidth=2, capsize=4, linewidth=2, label="Batch sync every k iterations")
    ax1.axhline(t_local, color="#2ca02c", linestyle="--", linewidth=1.8,
                label=f"Local accumulation (Approach 2): {t_local:.4f}s")
    ax1.axhline(t_per_hit, color="#d62728", linestyle=":", linewidth=1.8,
                label=f"Per-hit mutex (Approach 3): {t_per_hit:.4f}s")
    ax1.set_xscale("log")
    ax1.set_xlabel("Synchronization frequency k (iterations between updates)")
    ax1.set_ylabel("Mean execution time (s)")
    ax1.set_title(f"Execution Time vs Sync Frequency\n(N={points:,}, T={threads}, {len(means)} configs x 5 runs)")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(frameon=True, facecolor="white", fontsize=9)

    ax2.plot(ks, speedups, "-s", color="#1f77b4", linewidth=2, markersize=6,
             label="Speedup vs single thread")
    ax2.axhline(t_single / t_local, color="#2ca02c", linestyle="--", linewidth=1.8,
                label=f"Local accumulation: {t_single / t_local:.2f}x")
    ax2.axhline(1.0, color="#7f7f7f", linestyle=":", linewidth=1.3, label="Single-thread baseline")
    ax2.set_xscale("log")
    ax2.set_xlabel("Synchronization frequency k (iterations between updates)")
    ax2.set_ylabel("Speedup (x)")
    ax2.set_title(f"Speedup vs Sync Frequency\n(single-thread baseline: {t_single:.4f}s)")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(frameon=True, facecolor="white", fontsize=9)

    fig.tight_layout()
    out = os.path.join(GRAPH_DIR, "sync_frequency_vs_time.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
