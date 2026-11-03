#!/usr/bin/env python3
"""Build the figures and summary tables from the measured data.

Requires numpy and matplotlib (see requirements.txt). Run after
run_benchmarks.py. Paths are resolved relative to the package root.
"""

import csv
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MEASUREMENTS = ROOT / "2_measurements"
GRAPHS = ROOT / "3_graphs"
GRAPHS.mkdir(parents=True, exist_ok=True)

STYLE = {
    "a2": "#1f77b4",
    "a3": "#9467bd",
    "a1": "#ff7f0e",
    "core": "#d62728",
    "ideal": "#7f7f7f",
    "batch": "#2e7d32",
}


def load_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def load_section6():
    path = MEASUREMENTS / "section6_summary.csv"
    rows = []
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            rows.append({
                "approach": row["approach"],
                "threads": int(row["threads"]),
                "k": int(row["k"]),
                "runs": int(row["runs"]),
                "mean": float(row["average_seconds"]),
                "std": float(row["std_seconds"]),
                "pi": float(row["mean_pi"]),
            })
    return rows


def load_probe():
    path = MEASUREMENTS / "high_thread_probe_summary.csv"
    if not path.exists():
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            rows.append({
                "approach": row["approach"],
                "threads": int(row["threads"]),
                "mean": float(row["average_seconds"]),
                "std": float(row["std_seconds"]),
                "pi": float(row["mean_pi"]),
                "speedup": float(row["speedup"]),
            })
    return rows


def primary_series(data, key):
    items = data[key]
    return ([item["threads"] for item in items],
            [item["mean_time"] for item in items],
            [item["std_time"] for item in items],
            [item["speedup"] for item in items],
            [item["efficiency"] * 100 for item in items],
            [item["throughput_mpts"] for item in items])


def set_thread_axis(ax, threads):
    ax.set_xscale("log", base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], rotation=0, fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()


def plot_primary(data):
    cores = data["metadata"].get("affinity_cpus") or data["metadata"]["logical_cpus"]
    t1_mean = data["approach1_baseline"]["mean_time"]
    t2, m2, s2, sp2, e2, th2 = primary_series(data, "approach2_scaling")
    t3, m3, s3, sp3, e3, th3 = primary_series(data, "approach3_mutex_scaling")
    probe = load_probe()
    probe2 = sorted((row for row in probe if row["approach"] == "2"),
                    key=lambda row: row["threads"])
    probe3 = sorted((row for row in probe if row["approach"] == "3"),
                    key=lambda row: row["threads"])
    ticks = sorted(set(t2) | {row["threads"] for row in probe})
    points = data["metadata"]["total_points"]

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid"
                  in plt.style.available else "default")
    plt.rcParams.update({
        "font.size": 11, "axes.labelsize": 12, "axes.titlesize": 13,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
        "figure.titlesize": 14, "figure.dpi": 150,
    })

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.errorbar(t2, m2, yerr=s2, fmt="-o", color=STYLE["a2"], ecolor="#aec7e8",
                elinewidth=2, capsize=4, label="Approach 2 (Local Accumulation)", zorder=4)
    ax.errorbar(t3, m3, yerr=s3, fmt="-s", color=STYLE["a3"], ecolor="#c5b0d5",
                elinewidth=2, capsize=4, label="Approach 3 (Shared Mutex)", zorder=4)
    if probe2:
        ax.errorbar([row["threads"] for row in probe2],
                    [row["mean"] for row in probe2],
                    yerr=[row["std"] for row in probe2],
                    fmt="o", mfc="white", color=STYLE["a2"], ecolor="#aec7e8",
                    linestyle="none", markersize=8, capsize=4,
                    label="Approach 2 (256-512 probe)", zorder=5)
    if probe3:
        ax.errorbar([row["threads"] for row in probe3],
                    [row["mean"] for row in probe3],
                    yerr=[row["std"] for row in probe3],
                    fmt="s", mfc="white", color=STYLE["a3"], ecolor="#c5b0d5",
                    linestyle="none", markersize=8, capsize=4,
                    label="Approach 3 (256-512 probe)", zorder=5)
    ax.axhline(t1_mean, color=STYLE["a1"], linestyle=":", linewidth=1.8,
               label=f"Approach 1 Baseline ({t1_mean:.3f}s)")
    ax.axvline(cores, color=STYLE["core"], linestyle="--", linewidth=1.5, alpha=0.85,
               label=f"CPU Limit ({cores} Logical CPUs)")
    ax.set_title(f"Execution Time vs Threads (N={data['metadata']['total_points']:,})",
                 pad=12, fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Execution Time (s)")
    set_thread_axis(ax, ticks)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(GRAPHS / "execution_time_vs_threads.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ideal = [min(t, cores) for t in t2]
    ax.plot(t2, ideal, "--", color=STYLE["ideal"], linewidth=1.8,
            label=f"Ideal Linear Speedup (capped at {cores})")
    ax.plot(t2, sp2, "-s", color="#2ca02c", linewidth=2.2, markersize=7,
            label="Approach 2 Measured Speedup", zorder=4)
    ax.plot(t3, sp3, "-o", color=STYLE["a3"], linewidth=2.2, markersize=6,
            label="Approach 3 (Shared Mutex)", zorder=4)
    if probe2:
        ax.plot([row["threads"] for row in probe2],
                [row["speedup"] for row in probe2], "o", mfc="white",
                color="#2ca02c", markersize=9,
                label="Approach 2 (256-512 probe)", zorder=5)
    if probe3:
        ax.plot([row["threads"] for row in probe3],
                [row["speedup"] for row in probe3], "s", mfc="white",
                color=STYLE["a3"], markersize=9,
                label="Approach 3 (256-512 probe)", zorder=5)
    ax.axvline(cores, color=STYLE["core"], linestyle="--", linewidth=1.5, alpha=0.85,
               label=f"CPU Limit ({cores} Logical CPUs)")
    peak = int(np.argmax(sp2))
    ax.annotate(f"Peak: {sp2[peak]:.2f}x at {t2[peak]} threads",
                xy=(t2[peak], sp2[peak]),
                xytext=(t2[peak] * 1.7, sp2[peak] * 0.86),
                arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.5),
                fontweight="bold", color="#1b5e20")
    ax.set_title("Speedup vs Threads (S = T_single / T_parallel)", pad=12,
                 fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Speedup Factor (x)")
    set_thread_axis(ax, ticks)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(GRAPHS / "speedup_vs_threads.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(t2, e2, "-^", color=STYLE["a3"], linewidth=2.2, markersize=7,
            label="Approach 2 Efficiency (E = S / T)", zorder=4)
    ax.plot(t3, e3, "-o", color=STYLE["a1"], linewidth=2.2, markersize=6,
            label="Approach 3 Efficiency")
    ax.axhline(100.0, color=STYLE["ideal"], linestyle="--", linewidth=1.2,
               label="100% Ideal Efficiency")
    ax.axvline(cores, color=STYLE["core"], linestyle="--", linewidth=1.5, alpha=0.85,
               label=f"CPU Limit ({cores} Logical CPUs)")
    ax.set_title("Parallel Efficiency vs Threads", pad=12, fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Efficiency (%)")
    set_thread_axis(ax, ticks)
    ax.set_ylim(0, 110)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(GRAPHS / "parallel_efficiency_vs_threads.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(t2, th2, "-d", color=STYLE["core"], linewidth=2.2, markersize=7,
            label="Approach 2 Throughput", zorder=4)
    ax.plot(t3, th3, "-o", color=STYLE["a3"], linewidth=2.2, markersize=6,
            label="Approach 3 Throughput")
    if probe2:
        ax.plot([row["threads"] for row in probe2],
                [points / row["mean"] / 1e6 for row in probe2],
                "o", mfc="white", color=STYLE["core"], markersize=9,
                label="Approach 2 (256-512 probe)")
    if probe3:
        ax.plot([row["threads"] for row in probe3],
                [points / row["mean"] / 1e6 for row in probe3],
                "s", mfc="white", color=STYLE["a3"], markersize=9,
                label="Approach 3 (256-512 probe)")
    ax.axvline(cores, color=STYLE["a2"], linestyle="--", linewidth=1.5, alpha=0.85,
               label=f"CPU Limit ({cores} Logical CPUs)")
    ax.set_title("Throughput vs Threads", pad=12, fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Throughput (Million points / s)")
    set_thread_axis(ax, ticks)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(GRAPHS / "throughput_vs_threads.png")
    plt.close(fig)


def plot_section6(data, section6):
    cores = data["metadata"].get("affinity_cpus") or data["metadata"]["logical_cpus"]
    t1_mean = data["approach1_baseline"]["mean_time"]

    local = sorted((row for row in section6 if row["approach"] == "2"),
                   key=lambda row: row["threads"])
    shared = sorted((row for row in section6 if row["approach"] == "3"),
                    key=lambda row: row["threads"])
    batch = sorted((row for row in section6 if row["approach"] == "batch"),
                   key=lambda row: row["k"])

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.errorbar([r["threads"] for r in local], [r["mean"] for r in local],
                yerr=[r["std"] for r in local], fmt="-o", color=STYLE["a2"],
                ecolor="#aec7e8", elinewidth=2, capsize=4, label="Local accumulation")
    ax.axvline(cores, color=STYLE["core"], linestyle="--", linewidth=1.5,
               label=f"CPU Limit ({cores})")
    ax.set_xscale("log", base=2)
    threads = [r["threads"] for r in local]
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_title("Section 6.2: Thread Scaling (Local Accumulation)", pad=12,
                 fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Mean Execution Time (s)")
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white")
    fig.tight_layout()
    fig.savefig(GRAPHS / "section6_thread_scaling.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.errorbar([r["threads"] for r in local], [r["mean"] for r in local],
                yerr=[r["std"] for r in local], fmt="-o", color=STYLE["a2"],
                ecolor="#aec7e8", elinewidth=2, capsize=4, label="Local accumulation")
    ax.errorbar([r["threads"] for r in shared], [r["mean"] for r in shared],
                yerr=[r["std"] for r in shared], fmt="-s", color=STYLE["a3"],
                ecolor="#c5b0d5", elinewidth=2, capsize=4, label="Shared mutex")
    ax.axvline(cores, color=STYLE["core"], linestyle="--", linewidth=1.5,
               label=f"CPU Limit ({cores})")
    ax.set_xscale("log", base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_title("Section 6.3: Local vs Shared Accumulation", pad=12,
                 fontweight="bold")
    ax.set_xlabel("Number of Threads (T)")
    ax.set_ylabel("Mean Execution Time (s)")
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white")
    fig.tight_layout()
    fig.savefig(GRAPHS / "section6_local_vs_shared.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.errorbar([r["k"] for r in batch], [r["mean"] for r in batch],
                yerr=[r["std"] for r in batch], fmt="-o", color=STYLE["batch"],
                ecolor="#a5d6a7", elinewidth=2, capsize=4,
                label=f"Batch sync (T={batch[0]['threads']})")
    ax.set_xscale("log")
    ax.set_xticks([r["k"] for r in batch])
    ax.set_xticklabels([str(r["k"]) for r in batch])
    ax.minorticks_off()
    ax.set_title("Section 6.1: Synchronization Frequency", pad=12,
                 fontweight="bold")
    ax.set_xlabel("Iterations between mutex updates (k)")
    ax.set_ylabel("Mean Execution Time (s)")
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="white")
    fig.tight_layout()
    fig.savefig(GRAPHS / "section6_sync_frequency.png")
    plt.close(fig)


def render_tables(data, section6):
    meta = data["metadata"]
    baseline = data["approach1_baseline"]
    cores = meta.get("affinity_cpus") or meta["logical_cpus"]
    lines = []
    lines.append("# Performance Measurements\n")
    lines.append("Generated by `1_source_code/plot_results.py` from the raw CSV data.\n")
    lines.append(f"- Problem size: **N = {meta['total_points']:,}** points")
    lines.append(f"- Repetitions: **{meta['runs_per_config']}** runs per configuration")
    lines.append(f"- Master seed: `{meta['seed']}` (deterministic per-run derivation)")
    lines.append(f"- Environment: {meta['platform']}; {meta.get('processor', 'unknown CPU')}")
    lines.append(f"- CPU allocation: {cores} logical CPUs"
                 + (f" (`{meta['cpu_affinity_command']}`)" if meta.get("cpu_affinity_command") else ""))
    lines.append(f"- Compiler: {meta['compiler']}")
    lines.append(f"- Speedup: `S = T_single / T_parallel`; efficiency: `E = S / T`\n")

    lines.append("## Approach 1 - Single-thread baseline\n")
    lines.append("| Metric | Value |")
    lines.append("|:--|--:|")
    lines.append(f"| Mean execution time | **{baseline['mean_time']:.5f} s** |")
    lines.append(f"| Standard deviation | +/- {baseline['std_time']:.5f} s |")
    lines.append(f"| Throughput | {baseline['throughput_mpts']:.1f} Mpoints/s |")
    lines.append(f"| Estimated pi | {baseline['mean_pi']:.6f} |")
    lines.append(f"| Absolute error | {abs(baseline['mean_pi'] - 3.141592653589793):.6f} |\n")

    for key, title in (("approach2_scaling", "Approach 2 - Local accumulation"),
                       ("approach3_mutex_scaling", "Approach 3 - Shared mutex")):
        lines.append(f"## {title}\n")
        lines.append("| Threads | Mean time (s) | Std dev (s) | Speedup | Efficiency (%) | Throughput (Mpts/s) | Estimated pi |")
        lines.append("|:--:|--:|--:|--:|--:|--:|--:|")
        for item in data[key]:
            lines.append(
                f"| {item['threads']} | {item['mean_time']:.4f} | {item['std_time']:.4f} | "
                f"{item['speedup']:.2f}x | {item['efficiency'] * 100:.1f} | "
                f"{item['throughput_mpts']:.1f} | {item['mean_pi']:.6f} |"
            )
        lines.append("")

    probe = load_probe()
    if probe:
        lines.append("## High-thread probe (256 and 512 threads)\n")
        lines.append("Additional runs outside the 12-point sweep, used to resolve the "
                     "declining phase of the scaling curve. Same environment and "
                     "methodology; shown as hollow markers in the figures.\n")
        lines.append("| Approach | Threads | Mean time (s) | Std dev (s) | Speedup | Throughput (Mpts/s) |")
        lines.append("|:--:|--:|--:|--:|--:|--:|")
        for row in probe:
            label = "2 - Local" if row["approach"] == "2" else "3 - Mutex"
            lines.append(f"| {label} | {row['threads']} | {row['mean']:.4f} | "
                         f"{row['std']:.4f} | {row['speedup']:.2f}x | "
                         f"{meta['total_points'] / row['mean'] / 1e6:.1f} |")
        lines.append("")

    lines.append("## Section 6 - Trade-off experiments\n")
    lines.append(f"Section 6 uses the same environment, N = "
                 f"{meta['total_points']:,}, and {meta['runs_per_config']} runs per configuration.")
    batch_threads = meta.get("batch_threads") or cores
    lines.append(f"Batch synchronization uses T = {batch_threads}.\n")

    local = sorted((r for r in section6 if r["approach"] == "2"),
                   key=lambda r: r["threads"])
    shared = sorted((r for r in section6 if r["approach"] == "3"),
                    key=lambda r: r["threads"])
    batch = sorted((r for r in section6 if r["approach"] == "batch"),
                   key=lambda r: r["k"])

    lines.append("### 6.1 Synchronization frequency (batch variant)\n")
    lines.append("| k | Mean time (s) | Std dev (s) | Speedup vs single |")
    lines.append("|--:|--:|--:|--:|")
    for row in batch:
        lines.append(f"| {row['k']:,} | {row['mean']:.4f} | {row['std']:.4f} | "
                     f"{baseline['mean_time'] / row['mean']:.2f}x |")
    lines.append("")

    lines.append("### 6.2 Thread scaling (local accumulation)\n")
    lines.append("| Threads | Mean time (s) | Std dev (s) | Speedup vs single |")
    lines.append("|:--:|--:|--:|--:|")
    for row in local:
        lines.append(f"| {row['threads']} | {row['mean']:.4f} | {row['std']:.4f} | "
                     f"{baseline['mean_time'] / row['mean']:.2f}x |")
    lines.append("")

    lines.append("### 6.3 Local vs shared accumulation\n")
    lines.append("| Threads | Local mean (s) | Shared mean (s) | Ratio (shared/local) |")
    lines.append("|:--:|--:|--:|--:|")
    for local_row, shared_row in zip(local, shared):
        ratio = shared_row["mean"] / local_row["mean"]
        lines.append(f"| {local_row['threads']} | {local_row['mean']:.4f} | "
                     f"{shared_row['mean']:.4f} | {ratio:.2f}x |")
    lines.append("")
    lines.append("Raw data: `measurements.csv`, `benchmark_data.json`, "
                 "`section6_results.csv`, `section6_summary.csv`.\n")

    (MEASUREMENTS / "summary_tables.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    data = load_json(MEASUREMENTS / "benchmark_data.json")
    section6 = load_section6()
    plot_primary(data)
    plot_section6(data, section6)
    render_tables(data, section6)
    print(f"Generated 7 figures in {GRAPHS} and 2_measurements/summary_tables.md")


if __name__ == "__main__":
    main()
