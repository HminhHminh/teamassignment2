import subprocess
import json
import csv
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Ensure standard output doesn't crash on Windows cp1252 console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXE_PATH = os.path.join(BASE_DIR, "monte_carlo.exe")
if not os.path.isfile(EXE_PATH):
    # POSIX builds name the binary without the .exe suffix.
    EXE_PATH = os.path.join(BASE_DIR, "monte_carlo")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_test(approach, threads, points, k=1000, seed=123456789, runs=5):
    cmd = [
        EXE_PATH,
        "-a", str(approach),
        "-t", str(threads),
        "-n", str(points),
        "-k", str(k),
        "-s", str(seed),
        "-r", str(runs),
        "--csv"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR)
    if result.returncode != 0:
        raise RuntimeError(f"Benchmark command failed ({' '.join(cmd)}): {result.stderr}")
    
    records = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 7:
            records.append({
                "approach": parts[0],
                "threads": int(parts[1]),
                "points": int(parts[2]),
                "k": int(parts[3]),
                "run": int(parts[4]),
                "time": float(parts[5]),
                "pi": float(parts[6])
            })
    if len(records) != runs:
        raise RuntimeError(f"Expected {runs} benchmark records for approach {approach}, got {len(records)}")
    return records

def main():
    print("===================================================================")
    print(" EXECUTING BENCHMARKS: EXERCISE 3.1, 3.2 & 3.3")
    print("===================================================================")

    TOTAL_POINTS = 30000000  # 3 * 10^7 points
    RUNS = 5
    THREAD_COUNTS = [1, 2, 4, 6, 8, 12, 16, 24, 32, 64, 100, 128]

    # --- 3.1 Approach 1: Single Thread Baseline ---
    print(f"\n[1/3] Benchmarking Exercise 3.1: Single-Thread Baseline (N={TOTAL_POINTS}, runs={RUNS})...")
    app1_records = run_test("1", threads=1, points=TOTAL_POINTS, runs=RUNS)
    app1_times = [r["time"] for r in app1_records]
    app1_pis = [r["pi"] for r in app1_records]

    t_single_mean = float(np.mean(app1_times))
    t_single_std = float(np.std(app1_times))
    pi_single_mean = float(np.mean(app1_pis))
    thr_single = (TOTAL_POINTS / t_single_mean) / 1e6

    print(f" -> T_single Mean Time:  {t_single_mean:.6f} s (+/- {t_single_std:.6f} s)")
    print(f" -> Estimated Pi:        {pi_single_mean:.9f}")
    print(f" -> Single Throughput:   {thr_single:.2f} Mpoints/s")

    # --- 3.2 Approach 2: Multi-Thread Local Accumulation ---
    print(f"\n[2/3] Benchmarking Exercise 3.2: Multi-Thread Local Accumulation (Map-Reduce)...")
    app2_results = []
    csv_rows = []

    # Add Approach 1 to CSV rows
    for r in app1_records:
        csv_rows.append({
            "approach": "1_SingleThread",
            "threads": 1,
            "points": TOTAL_POINTS,
            "run": r["run"],
            "time": r["time"],
            "speedup": 1.0,
            "efficiency": 1.0,
            "throughput_mpts": (TOTAL_POINTS / r["time"]) / 1e6,
            "pi": r["pi"]
        })

    for t in THREAD_COUNTS:
        records = run_test("2", threads=t, points=TOTAL_POINTS, runs=RUNS)
        times = [r["time"] for r in records]
        pis = [r["pi"] for r in records]
        
        mean_t = float(np.mean(times))
        std_t = float(np.std(times))
        mean_pi = float(np.mean(pis))
        speedup = t_single_mean / mean_t
        efficiency = speedup / t
        throughput = (TOTAL_POINTS / mean_t) / 1e6

        print(f" -> Threads: {t:3d} | Time: {mean_t:.5f}s (+/-{std_t:.5f}s) | Speedup: {speedup:5.2f}x | Eff: {efficiency*100:5.1f}% | Thr: {throughput:7.1f} Mpts/s | Pi: {mean_pi:.7f}")

        app2_results.append({
            "threads": t,
            "mean_time": mean_t,
            "std_time": std_t,
            "speedup": speedup,
            "efficiency": efficiency,
            "throughput_mpts": throughput,
            "mean_pi": mean_pi,
            "runs": times
        })

        for r in records:
            csv_rows.append({
                "approach": "2_LocalAccumulation",
                "threads": t,
                "points": TOTAL_POINTS,
                "run": r["run"],
                "time": r["time"],
                "speedup": t_single_mean / r["time"],
                "efficiency": (t_single_mean / r["time"]) / t,
                "throughput_mpts": (TOTAL_POINTS / r["time"]) / 1e6,
                "pi": r["pi"]
            })

    # --- 3.3 Approach 3: Shared Variable with Mutex ---
    print("\n[3/3] Benchmarking Exercise 3.3: Shared Counter with Mutex...")
    app3_results = []
    for t in THREAD_COUNTS:
        records = run_test("3", threads=t, points=TOTAL_POINTS, runs=RUNS)
        times = [r["time"] for r in records]
        pis = [r["pi"] for r in records]

        mean_t = float(np.mean(times))
        std_t = float(np.std(times))
        mean_pi = float(np.mean(pis))
        speedup = t_single_mean / mean_t
        efficiency = speedup / t
        throughput = (TOTAL_POINTS / mean_t) / 1e6

        print(f" -> Threads: {t:3d} | Time: {mean_t:.5f}s (+/-{std_t:.5f}s) | Speedup: {speedup:5.2f}x | Eff: {efficiency*100:5.1f}% | Thr: {throughput:7.1f} Mpts/s | Pi: {mean_pi:.7f}")

        app3_results.append({
            "threads": t,
            "mean_time": mean_t,
            "std_time": std_t,
            "speedup": speedup,
            "efficiency": efficiency,
            "throughput_mpts": throughput,
            "mean_pi": mean_pi,
            "runs": times
        })

        for r in records:
            csv_rows.append({
                "approach": "3_SharedMutex",
                "threads": t,
                "points": TOTAL_POINTS,
                "run": r["run"],
                "time": r["time"],
                "speedup": t_single_mean / r["time"],
                "efficiency": (t_single_mean / r["time"]) / t,
                "throughput_mpts": (TOTAL_POINTS / r["time"]) / 1e6,
                "pi": r["pi"]
            })

    # Save benchmark data JSON
    data_output = {
        "metadata": {
            "total_points": TOTAL_POINTS,
            "runs_per_config": RUNS,
            "cpu_cores_logical": os.cpu_count()
        },
        "approach1_baseline": {
            "points": TOTAL_POINTS,
            "mean_time": t_single_mean,
            "std_time": t_single_std,
            "mean_pi": pi_single_mean,
            "throughput_mpts": thr_single,
            "runs": app1_times
        },
        "approach2_scaling": app2_results,
        "approach3_mutex_scaling": app3_results
    }

    json_path = os.path.join(RESULTS_DIR, "benchmark_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data_output, f, indent=2)
    print("\nSaved benchmark data JSON successfully.")

    # Save CSV
    csv_path = os.path.join(RESULTS_DIR, "measurements.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["approach", "threads", "points", "run", "time", "speedup", "efficiency", "throughput_mpts", "pi"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print("Saved measurements CSV successfully.")

    # --- PLOTTING ---
    print("\nGenerating publication-quality figures...")
    generate_figures(data_output)
    print("All figures generated in results/ directory!")

def generate_figures(data):
    app2 = data["approach2_scaling"]
    app3 = data["approach3_mutex_scaling"]
    t1_mean = data["approach1_baseline"]["mean_time"]
    threads = [x["threads"] for x in app2]
    times = [x["mean_time"] for x in app2]
    stds = [x["std_time"] for x in app2]
    speedups = [x["speedup"] for x in app2]
    efficiencies = [x["efficiency"] * 100 for x in app2]
    throughputs = [x["throughput_mpts"] for x in app2]
    app3_threads = [x["threads"] for x in app3]
    app3_times = [x["mean_time"] for x in app3]
    app3_stds = [x["std_time"] for x in app3]
    app3_speedups = [x["speedup"] for x in app3]
    app3_efficiencies = [x["efficiency"] * 100 for x in app3]
    app3_throughputs = [x["throughput_mpts"] for x in app3]
    cores = data["metadata"]["cpu_cores_logical"]

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams.update({
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 11,
        'figure.titlesize': 14,
        'figure.dpi': 300
    })

    # 1. Execution Time vs Threads
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.errorbar(threads, times, yerr=stds, fmt='-o', color='#1f77b4', ecolor='#aec7e8',
                elinewidth=2, capsize=4, label='Approach 2 (Local Accumulation)', zorder=4)
    ax.errorbar(app3_threads, app3_times, yerr=app3_stds, fmt='-s', color='#9467bd', ecolor='#c5b0d5',
                elinewidth=2, capsize=4, label='Approach 3 (Shared Mutex)', zorder=4)
    ax.axhline(y=t1_mean, color='#ff7f0e', linestyle=':', linewidth=1.8, label=f'Approach 1 Baseline (Single Thread: {t1_mean:.3f}s)')
    ax.axvline(x=cores, color='#d62728', linestyle='--', linewidth=1.5, alpha=0.85, label=f'Hardware Core Limit ({cores} Cores)')

    ax.set_title(f'Monte Carlo Pi Estimation: Execution Time vs Number of Threads (N={data["metadata"]["total_points"]:,})', pad=12, fontweight='bold')
    ax.set_xlabel('Number of Threads (T)')
    ax.set_ylabel('Execution Time (seconds)')
    ax.set_xscale('log', base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], rotation=0, fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "execution_time_vs_threads.png"))
    plt.close()

    # 2. Speedup vs Threads
    fig, ax = plt.subplots(figsize=(8.5, 5))
    # Ideal linear speedup up to cores, then plateau
    ideal_speedup = [min(t, cores) for t in threads]
    ax.plot(threads, ideal_speedup, '--', color='#7f7f7f', linewidth=1.8, label=f'Ideal Linear Speedup (capped at {cores} cores)')
    ax.plot(threads, speedups, '-s', color='#2ca02c', linewidth=2.2, markersize=7, label='Approach 2 Measured Speedup', zorder=4)
    ax.plot(app3_threads, app3_speedups, '-o', color='#9467bd', linewidth=2.2, markersize=6, label='Approach 3 (Shared Mutex)', zorder=4)
    ax.axvline(x=cores, color='#d62728', linestyle='--', linewidth=1.5, alpha=0.85, label=f'CPU Hardware Saturation ({cores} Cores)')

    # Annotate maximum speedup
    max_idx = int(np.argmax(speedups))
    ax.annotate(f'Peak: {speedups[max_idx]:.2f}x at {threads[max_idx]} threads',
                xy=(threads[max_idx], speedups[max_idx]),
                xytext=(threads[max_idx] + 8, speedups[max_idx] * 0.85),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.5),
                fontweight='bold', color='#1b5e20')

    ax.set_title(f'Speedup vs Number of Threads ($S = T_{{single}} / T_{{parallel}}$)', pad=12, fontweight='bold')
    ax.set_xlabel('Number of Threads (T)')
    ax.set_ylabel('Speedup Factor (x)')
    ax.set_xscale('log', base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], rotation=0, fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "speedup_vs_threads.png"))
    plt.close()

    # 3. Parallel Efficiency vs Threads
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(threads, efficiencies, '-^', color='#9467bd', linewidth=2.2, markersize=7, label='Parallel Efficiency ($E = S / T$)', zorder=4)
    ax.plot(app3_threads, app3_efficiencies, '-o', color='#ff7f0e', linewidth=2.2, markersize=6, label='Approach 3 (Shared Mutex)', zorder=4)
    ax.axhline(y=100.0, color='#7f7f7f', linestyle='--', linewidth=1.2, label='100% Ideal Efficiency')
    ax.axvline(x=cores, color='#d62728', linestyle='--', linewidth=1.5, alpha=0.85, label=f'CPU Hardware Limit ({cores} Cores)')

    ax.set_title('Parallel Efficiency vs Number of Threads', pad=12, fontweight='bold')
    ax.set_xlabel('Number of Threads (T)')
    ax.set_ylabel('Efficiency (%)')
    ax.set_xscale('log', base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], rotation=0, fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_ylim(0, 110)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "parallel_efficiency_vs_threads.png"))
    plt.close()

    # 4. Throughput vs Threads
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.plot(threads, throughputs, '-d', color='#d62728', linewidth=2.2, markersize=7, label='Throughput (Million points/s)', zorder=4)
    ax.plot(app3_threads, app3_throughputs, '-o', color='#9467bd', linewidth=2.2, markersize=6, label='Approach 3 (Shared Mutex)', zorder=4)
    ax.axvline(x=cores, color='#1f77b4', linestyle='--', linewidth=1.5, alpha=0.85, label=f'CPU Saturation ({cores} Cores)')

    ax.set_title('Throughput vs Number of Threads', pad=12, fontweight='bold')
    ax.set_xlabel('Number of Threads (T)')
    ax.set_ylabel('Throughput (Million points / sec)')
    ax.set_xscale('log', base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], rotation=0, fontsize=9)
    ax.set_xlim(0.8, threads[-1] * 1.25)
    ax.minorticks_off()
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "throughput_vs_threads.png"))
    plt.close()

if __name__ == "__main__":
    main()
