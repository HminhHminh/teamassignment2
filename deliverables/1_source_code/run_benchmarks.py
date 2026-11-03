#!/usr/bin/env python3
"""Run every measurement used in this submission.

The script uses only the Python standard library, so it can run in a minimal
Linux environment. It writes:

    2_measurements/measurements.csv        raw runs, Approaches 1-3
    2_measurements/benchmark_data.json     aggregated primary benchmark
    2_measurements/section6_results.csv    raw runs, Section 6
    2_measurements/section6_summary.csv    aggregated Section 6
    2_measurements/environment.json        machine / compiler description

By default the benchmark is pinned to 2 logical CPUs with ``taskset`` on Linux
to match the submitted environment. Use ``--no-affinity`` to run on all CPUs.

Examples:
    python3 run_benchmarks.py --exe ./monte_carlo --cpus 2
    python3 run_benchmarks.py --quick          # smoke test, not submittable
"""

import argparse
import csv
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "1_source_code"
MEASUREMENTS_DIR = ROOT / "2_measurements"

PRIMARY_THREADS = [1, 2, 4, 6, 8, 12, 16, 24, 32, 64, 100, 128]
PROBE_THREADS = [256, 512]
SECTION6_THREADS = [1, 2, 4, 8, 16, 100]
SECTION6_K = [1, 10, 100, 1000]
POINTS = 30_000_000
RUNS = 5
SEED = 123456789


def find_executable(override):
    candidates = [
        override,
        os.environ.get("MONTE_CARLO_EXE", ""),
        str(SRC_DIR / "monte_carlo"),
        str(SRC_DIR / "monte_carlo.exe"),
        str(SRC_DIR / "build" / "monte_carlo"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise SystemExit(
        "monte_carlo executable not found. Build it first (make / build.bat) "
        "or pass --exe PATH."
    )


def compiler_version():
    for command in (["gcc", "--version"], ["cc", "--version"]):
        try:
            output = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, check=True
            ).stdout.splitlines()
            if output:
                return output[0].strip()
        except (OSError, subprocess.CalledProcessError):
            continue
    return "unknown"


def affinity_prefix(cpus):
    if cpus <= 0:
        return []
    if platform.system() == "Linux" and shutil.which("taskset"):
        return ["taskset", "-c", f"0-{cpus - 1}"]
    return []


def run_case(exe, approach, threads, points, runs, k=1000, prefix=None):
    prefix = prefix or []
    command = [
        *prefix, exe,
        "-a", str(approach),
        "-t", str(threads),
        "-n", str(points),
        "-k", str(k),
        "-s", str(SEED),
        "-r", str(runs),
        "--csv",
    ]
    completed = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({' '.join(command)}):\n{completed.stderr}"
        )

    records = []
    for line in completed.stdout.strip().splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 7:
            continue
        records.append({
            "approach": fields[0],
            "threads": int(fields[1]),
            "points": int(fields[2]),
            "k": int(fields[3]),
            "run": int(fields[4]),
            "time": float(fields[5]),
            "pi": float(fields[6]),
        })
    if len(records) != runs:
        raise RuntimeError(
            f"expected {runs} records for approach {approach}, got {len(records)}"
        )
    return records


def summarize(records, reference_time=None, threads=None):
    times = [record["time"] for record in records]
    mean_time = statistics.mean(times)
    item = {
        "threads": threads if threads is not None else records[0]["threads"],
        "mean_time": mean_time,
        "std_time": statistics.pstdev(times),
        "mean_pi": statistics.mean(record["pi"] for record in records),
        "runs": times,
    }
    if reference_time:
        item["speedup"] = reference_time / mean_time
        item["efficiency"] = item["speedup"] / item["threads"]
        item["throughput_mpts"] = (records[0]["points"] / mean_time) / 1e6
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", default="", help="path to the monte_carlo binary")
    parser.add_argument("--points", type=int, default=POINTS)
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--cpus", type=int, default=2,
                        help="pin to this many logical CPUs (Linux taskset); 0 disables")
    parser.add_argument("--no-affinity", action="store_true")
    parser.add_argument("--quick", action="store_true",
                        help="small smoke-test configuration (not submittable)")
    args = parser.parse_args()

    if args.quick:
        args.points = 2_000_000
        args.runs = 2
        primary_threads = [1, 2, 4, 8, 100]
        section6_threads = [1, 2, 8]
        section6_k = [1, 100]
    else:
        primary_threads = PRIMARY_THREADS
        section6_threads = SECTION6_THREADS
        section6_k = SECTION6_K

    exe = find_executable(args.exe)
    cpus = 0 if args.no_affinity else args.cpus
    prefix = affinity_prefix(cpus)
    MEASUREMENTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print(" Monte Carlo pi benchmark")
    print(f" executable : {exe}")
    print(f" points     : {args.points:,}")
    print(f" runs/config: {args.runs}")
    print(f" affinity   : {prefix or 'none (all CPUs)'}")
    print("=" * 72)

    baseline_raw = run_case(exe, 1, 1, args.points, args.runs, prefix=prefix)
    baseline = summarize(baseline_raw, threads=1)
    baseline["points"] = args.points
    baseline["throughput_mpts"] = (args.points / baseline["mean_time"]) / 1e6
    print(f"Approach 1: {baseline['mean_time']:.6f} s, "
          f"pi={baseline['mean_pi']:.9f}")

    primary_rows = []
    for record in baseline_raw:
        primary_rows.append({
            "approach": "1_SingleThread",
            "threads": 1,
            "points": args.points,
            "run": record["run"],
            "time": record["time"],
            "speedup": 1.0,
            "efficiency": 1.0,
            "throughput_mpts": (args.points / record["time"]) / 1e6,
            "pi": record["pi"],
        })

    approach2 = []
    for threads in primary_threads:
        records = run_case(exe, 2, threads, args.points, args.runs, prefix=prefix)
        item = summarize(records, baseline["mean_time"], threads)
        item["points"] = args.points
        approach2.append(item)
        print(f"A2 T={threads:3d}: {item['mean_time']:.6f} s  "
              f"S={item['speedup']:.2f}x  E={item['efficiency'] * 100:.1f}%")
        for record in records:
            primary_rows.append({
                "approach": "2_LocalAccumulation",
                "threads": threads,
                "points": args.points,
                "run": record["run"],
                "time": record["time"],
                "speedup": baseline["mean_time"] / record["time"],
                "efficiency": (baseline["mean_time"] / record["time"]) / threads,
                "throughput_mpts": (args.points / record["time"]) / 1e6,
                "pi": record["pi"],
            })

    approach3 = []
    for threads in primary_threads:
        records = run_case(exe, 3, threads, args.points, args.runs, prefix=prefix)
        item = summarize(records, baseline["mean_time"], threads)
        item["points"] = args.points
        approach3.append(item)
        print(f"A3 T={threads:3d}: {item['mean_time']:.6f} s  "
              f"S={item['speedup']:.2f}x  E={item['efficiency'] * 100:.1f}%")
        for record in records:
            primary_rows.append({
                "approach": "3_SharedMutex",
                "threads": threads,
                "points": args.points,
                "run": record["run"],
                "time": record["time"],
                "speedup": baseline["mean_time"] / record["time"],
                "efficiency": (baseline["mean_time"] / record["time"]) / threads,
                "throughput_mpts": (args.points / record["time"]) / 1e6,
                "pi": record["pi"],
            })

    probe_rows = []
    probe_summary = []
    if args.quick:
        for name in ("high_thread_probe.csv", "high_thread_probe_summary.csv"):
            path = MEASUREMENTS_DIR / name
            if path.exists():
                path.unlink()
    else:
        for threads in PROBE_THREADS:
            for approach in (2, 3):
                records = run_case(exe, approach, threads, args.points, args.runs,
                                   prefix=prefix)
                probe_rows.extend(records)
                item = summarize(records, baseline["mean_time"], threads)
                probe_summary.append({
                    "approach": str(approach),
                    "threads": threads,
                    "runs": len(records),
                    "average_seconds": item["mean_time"],
                    "std_seconds": item["std_time"],
                    "mean_pi": item["mean_pi"],
                    "speedup": item["speedup"],
                })
                print(f"probe A{approach} T={threads:3d}: "
                      f"{item['mean_time']:.6f} s  S={item['speedup']:.2f}x")

        with open(MEASUREMENTS_DIR / "high_thread_probe.csv", "w", newline="",
                  encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "approach", "threads", "points", "k", "run", "time", "pi",
            ])
            writer.writeheader()
            writer.writerows(probe_rows)

        with open(MEASUREMENTS_DIR / "high_thread_probe_summary.csv", "w",
                  newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "approach", "threads", "runs", "average_seconds",
                "std_seconds", "mean_pi", "speedup",
            ])
            writer.writeheader()
            writer.writerows(probe_summary)

    measurements_path = MEASUREMENTS_DIR / "measurements.csv"
    with open(measurements_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "approach", "threads", "points", "run", "time",
            "speedup", "efficiency", "throughput_mpts", "pi",
        ])
        writer.writeheader()
        writer.writerows(primary_rows)

    batch_threads = cpus if cpus else 2
    section6_rows = []
    local_runs = {}
    shared_runs = {}
    for threads in section6_threads:
        local = run_case(exe, 2, threads, args.points, args.runs, prefix=prefix)
        shared = run_case(exe, 3, threads, args.points, args.runs, prefix=prefix)
        local_runs[threads] = local
        shared_runs[threads] = shared
        section6_rows.extend(local)
        section6_rows.extend(shared)
        print(f"6.2/6.3 T={threads:3d}: local "
              f"{statistics.mean(r['time'] for r in local):.6f} s, shared "
              f"{statistics.mean(r['time'] for r in shared):.6f} s")

    for frequency in section6_k:
        records = run_case(exe, "batch", batch_threads, args.points, args.runs,
                           k=frequency, prefix=prefix)
        section6_rows.extend(records)
        print(f"6.1 k={frequency:6d}: "
              f"{statistics.mean(r['time'] for r in records):.6f} s")

    section6_path = MEASUREMENTS_DIR / "section6_results.csv"
    with open(section6_path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "approach", "threads", "points", "k", "run", "time", "pi",
        ])
        writer.writeheader()
        writer.writerows(section6_rows)

    grouped = {}
    for record in section6_rows:
        key = (record["approach"], record["threads"], record["k"])
        grouped.setdefault(key, []).append(record)
    section6_summary = []
    for key in sorted(grouped):
        records = grouped[key]
        section6_summary.append({
            "approach": key[0],
            "threads": key[1],
            "k": key[2],
            "runs": len(records),
            "average_seconds": statistics.mean(r["time"] for r in records),
            "std_seconds": statistics.pstdev(r["time"] for r in records),
            "mean_pi": statistics.mean(r["pi"] for r in records),
        })
    with open(MEASUREMENTS_DIR / "section6_summary.csv", "w", newline="",
              encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "approach", "threads", "k", "runs", "average_seconds",
            "std_seconds", "mean_pi",
        ])
        writer.writeheader()
        writer.writerows(section6_summary)

    metadata = {
        "total_points": args.points,
        "runs_per_config": args.runs,
        "seed": SEED,
        "logical_cpus": os.cpu_count(),
        "affinity_cpus": cpus if prefix else None,
        "batch_threads": batch_threads,
        "cpu_affinity_command": " ".join(prefix) if prefix else None,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "compiler": compiler_version(),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    data_output = {
        "metadata": metadata,
        "approach1_baseline": baseline,
        "approach2_scaling": approach2,
        "approach3_mutex_scaling": approach3,
    }
    with open(MEASUREMENTS_DIR / "benchmark_data.json", "w", encoding="utf-8") as stream:
        json.dump(data_output, stream, indent=2)

    with open(MEASUREMENTS_DIR / "environment.json", "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)

    print("\nWrote measurements.csv, benchmark_data.json, section6_*.csv, "
          "high_thread_probe*.csv, environment.json")
    print(f"Approach 1 baseline: {baseline['mean_time']:.6f} s")
    print("Next: python3 plot_results.py  (or plot_results.py on Windows)")


if __name__ == "__main__":
    sys.exit(main())
