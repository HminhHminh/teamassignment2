#!/usr/bin/env python3
"""Verify the submission package for internal consistency and correctness.

Checks (hard errors):
  * all required files exist and the graphs are valid PNGs;
  * every configuration has exactly 5 runs and the expected thread counts;
  * CSV and JSON agree on means, standard deviations, speedups, efficiency
    and throughput;
  * Approaches 2 and 3 produce identical pi values per thread count, batch
    frequencies reproduce the same pi, and all estimates are statistically
    plausible for N = 30M;
  * relative Markdown links resolve;
  * no superseded datasets remain in the package.

Trend checks (warnings unless --strict):
  * local accumulation beats the shared mutex and scales at 2 threads;
  * per-hit locking is slower than the baseline;
  * batching at k = 1000 is much faster than per-hit batching;
  * the plateau does not collapse at high thread counts.

Usage:
    python3 verify.py            # warnings allowed
    python3 verify.py --strict   # warnings fail the run
"""

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEASUREMENTS = ROOT / "2_measurements"
GRAPHS = ROOT / "3_graphs"
PI_TRUE = 3.141592653589793
POINTS = 30_000_000
RUNS = 5
PRIMARY_THREADS = [1, 2, 4, 6, 8, 12, 16, 24, 32, 64, 100, 128]
SECTION6_THREADS = [1, 2, 4, 8, 16, 100]
SECTION6_K = [1, 10, 100, 1000]
PROBE_THREADS = [256, 512]
GRAPH_FILES = [
    "execution_time_vs_threads.png",
    "speedup_vs_threads.png",
    "parallel_efficiency_vs_threads.png",
    "throughput_vs_threads.png",
    "section6_thread_scaling.png",
    "section6_local_vs_shared.png",
    "section6_sync_frequency.png",
]
REQUIRED_FILES = [
    "README.md",
    "requirements.txt",
    "reproduce.sh",
    "reproduce.bat",
    "verify.py",
    "1_source_code/README.md",
    "1_source_code/Makefile",
    "1_source_code/src/common.h",
    "1_source_code/src/approach1_single.c",
    "1_source_code/src/approach2_local.c",
    "1_source_code/src/approach3_mutex.c",
    "1_source_code/src/approach3_batch.c",
    "1_source_code/src/main.c",
    "1_source_code/run_benchmarks.py",
    "1_source_code/plot_results.py",
    "2_measurements/measurements.csv",
    "2_measurements/benchmark_data.json",
    "2_measurements/summary_tables.md",
    "2_measurements/section6_results.csv",
    "2_measurements/section6_summary.csv",
    "2_measurements/high_thread_probe.csv",
    "2_measurements/high_thread_probe_summary.csv",
    "2_measurements/environment.json",
    "4_analysis/analysis_report.md",
    "5_best_practices/best_practices.md",
]
LEGACY_FILES = [
    "1_source_code/run_experiments.py",
    "2_measurements/run_sync_frequency.py",
    "2_measurements/sync_frequency_runs.csv",
    "2_measurements/sync_frequency_summary.csv",
    "2_measurements/sync_frequency_metadata.json",
    "3_graphs/sync_frequency_vs_time.png",
]


class Checker:
    def __init__(self):
        self.passed = 0
        self.errors = []
        self.warnings = []

    def ok(self, condition, message):
        if condition:
            self.passed += 1
        else:
            self.errors.append(message)

    def close(self, actual, expected, tolerance, message):
        self.ok(abs(actual - expected) <= tolerance,
                f"{message} (got {actual!r}, expected {expected!r} +/- {tolerance})")

    def trend(self, condition, message):
        if condition:
            self.passed += 1
        else:
            self.warnings.append(message)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def group(rows, *keys):
    buckets = defaultdict(list)
    for row in rows:
        buckets[tuple(row[key] for key in keys)].append(row)
    return buckets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="treat trend warnings as errors")
    args = parser.parse_args()
    check = Checker()

    # ------------------------------------------------------------------ files
    for relative in REQUIRED_FILES:
        check.ok((ROOT / relative).is_file(), f"missing required file: {relative}")
    for relative in LEGACY_FILES:
        check.ok(not (ROOT / relative).exists(),
                 f"superseded file still present: {relative}")
    for name in GRAPH_FILES:
        path = GRAPHS / name
        exists = path.is_file()
        check.ok(exists, f"missing graph: {name}")
        if exists:
            data = path.read_bytes()
            check.ok(data[:8] == b"\x89PNG\r\n\x1a\n",
                     f"not a valid PNG: {name}")
            check.ok(len(data) > 20000, f"graph looks empty: {name}")

    if check.errors:
        report(check, args.strict)
        return 1

    # --------------------------------------------------------------- sources
    makefile = (ROOT / "1_source_code" / "Makefile").read_text(encoding="utf-8")
    check.ok("-O3" in makefile, "Makefile does not use -O3")
    check.ok("-pthread" in makefile, "Makefile does not use -pthread")
    common = (ROOT / "1_source_code" / "src" / "common.h").read_text(encoding="utf-8")
    check.ok("StartGate" in common, "common.h is missing the StartGate")
    check.ok("CLOCK_MONOTONIC" in common, "common.h does not use CLOCK_MONOTONIC")
    for source in ("approach2_local.c", "approach3_mutex.c", "approach3_batch.c"):
        text = (ROOT / "1_source_code" / "src" / source).read_text(encoding="utf-8")
        check.ok("finished_at" in text, f"{source} does not record finished_at")

    # ------------------------------------------------------------- environment
    env = json.loads((MEASUREMENTS / "environment.json").read_text(encoding="utf-8"))
    check.ok(env.get("total_points") == POINTS, "environment: wrong point count")
    check.ok(env.get("runs_per_config") == RUNS, "environment: wrong run count")
    check.ok(env.get("seed") == 123456789, "environment: wrong master seed")
    check.ok(env.get("compiler", "unknown") != "unknown",
             "environment: compiler not recorded")

    # ---------------------------------------------------------- measurements
    rows = read_csv(MEASUREMENTS / "measurements.csv")
    expected_rows = RUNS * (1 + 2 * len(PRIMARY_THREADS))
    check.ok(len(rows) == expected_rows,
             f"measurements.csv: {len(rows)} rows, expected {expected_rows}")

    for row in rows:
        row["threads"] = int(row["threads"])
        row["points"] = int(row["points"])
        row["run"] = int(row["run"])
        row["time"] = float(row["time"])
        row["speedup"] = float(row["speedup"])
        row["efficiency"] = float(row["efficiency"])
        row["throughput_mpts"] = float(row["throughput_mpts"])
        row["pi"] = float(row["pi"])
        check.ok(row["points"] == POINTS, "measurements.csv: wrong point count")
        check.ok(row["time"] > 0, "measurements.csv: non-positive time")
        check.ok(abs(row["pi"] - PI_TRUE) <= 0.0015,
                 f"measurements.csv: implausible pi {row['pi']}")

    buckets = group(rows, "approach", "threads")
    for (approach, threads), items in buckets.items():
        check.ok(len(items) == RUNS,
                 f"{approach} T={threads}: {len(items)} runs, expected {RUNS}")
        check.ok(sorted(item["run"] for item in items) == list(range(1, RUNS + 1)),
                 f"{approach} T={threads}: run numbers are not 1..{RUNS}")

    check.ok(set(key[0] for key in buckets) ==
             {"1_SingleThread", "2_LocalAccumulation", "3_SharedMutex"},
             "measurements.csv: unexpected approach names")
    for approach in ("2_LocalAccumulation", "3_SharedMutex"):
        threads = sorted(key[1] for key in buckets if key[0] == approach)
        check.ok(threads == PRIMARY_THREADS,
                 f"{approach}: thread counts {threads} != {PRIMARY_THREADS}")

    # ---------------------------------------------------------------- json
    data = json.loads((MEASUREMENTS / "benchmark_data.json").read_text(encoding="utf-8"))
    baseline = data["approach1_baseline"]
    baseline_rows = buckets[("1_SingleThread", 1)]
    baseline_mean = statistics.mean(row["time"] for row in baseline_rows)
    baseline_std = statistics.pstdev(row["time"] for row in baseline_rows)
    baseline_pi = statistics.mean(row["pi"] for row in baseline_rows)
    check.close(baseline["mean_time"], baseline_mean, 1e-12,
                "baseline mean time differs between CSV and JSON")
    check.close(baseline["std_time"], baseline_std, 1e-12,
                "baseline std differs between CSV and JSON")
    check.close(baseline["mean_pi"], baseline_pi, 1e-12,
                "baseline pi differs between CSV and JSON")
    check.close(baseline["throughput_mpts"], POINTS / baseline_mean / 1e6, 1e-9,
                "baseline throughput is inconsistent")
    check.ok(abs(baseline_pi - PI_TRUE) <= 0.0008,
             f"baseline pi error too large: {baseline_pi}")

    # Approach 1 and Approach 2/T=1 share their seed and partition.
    for left, right in zip(sorted(baseline_rows, key=lambda row: row["run"]),
                           sorted(buckets[("2_LocalAccumulation", 1)],
                                  key=lambda row: row["run"])):
        check.close(left["pi"], right["pi"], 1e-12,
                    "Approach 1 and Approach 2 T=1 disagree on pi")

    for key, title in (("approach2_scaling", "Approach 2"),
                       ("approach3_mutex_scaling", "Approach 3")):
        items = data[key]
        check.ok(len(items) == len(PRIMARY_THREADS),
                 f"{title}: wrong number of configurations")
        seen = set()
        for item in items:
            threads = item["threads"]
            seen.add(threads)
            approach = "2_LocalAccumulation" if key == "approach2_scaling" else "3_SharedMutex"
            records = buckets.get((approach, threads), [])
            check.ok(len(records) == RUNS, f"{title} T={threads}: wrong run count")
            if len(records) != RUNS:
                continue
            times = [row["time"] for row in records]
            mean = statistics.mean(times)
            std = statistics.pstdev(times)
            pi = statistics.mean(row["pi"] for row in records)
            check.close(item["mean_time"], mean, 1e-12,
                        f"{title} T={threads}: mean mismatch")
            check.close(item["std_time"], std, 1e-12,
                        f"{title} T={threads}: std mismatch")
            check.close(item["mean_pi"], pi, 1e-12,
                        f"{title} T={threads}: pi mismatch")
            check.close(item["speedup"], baseline_mean / mean, 1e-12,
                        f"{title} T={threads}: speedup mismatch")
            check.close(item["efficiency"], (baseline_mean / mean) / threads, 1e-12,
                        f"{title} T={threads}: efficiency mismatch")
            check.close(item["throughput_mpts"], POINTS / mean / 1e6, 1e-9,
                        f"{title} T={threads}: throughput mismatch")
            for row in records:
                check.close(row["speedup"], baseline_mean / row["time"], 1e-9,
                            f"{title} T={threads} run {row['run']}: row speedup mismatch")
                check.close(row["efficiency"],
                            (baseline_mean / row["time"]) / threads, 1e-9,
                            f"{title} T={threads} run {row['run']}: row efficiency mismatch")
                check.close(row["throughput_mpts"],
                            POINTS / row["time"] / 1e6, 1e-9,
                            f"{title} T={threads} run {row['run']}: row throughput mismatch")
                check.close(row["pi"], pi, 0.0015,
                            f"{title} T={threads} run {row['run']}: pi far from group mean")
        check.ok(seen == set(PRIMARY_THREADS), f"{title}: missing thread counts")

    # Approaches 2 and 3 must agree exactly for every (T, run).
    for threads in PRIMARY_THREADS:
        local = sorted(buckets[("2_LocalAccumulation", threads)],
                       key=lambda row: row["run"])
        shared = sorted(buckets[("3_SharedMutex", threads)],
                        key=lambda row: row["run"])
        for left, right in zip(local, shared):
            check.close(left["pi"], right["pi"], 1e-12,
                        f"T={threads} run {left['run']}: local/shared pi mismatch")

    # -------------------------------------------------------------- section 6
    section6 = read_csv(MEASUREMENTS / "section6_results.csv")
    for row in section6:
        row["threads"] = int(row["threads"])
        row["k"] = int(row["k"])
        row["run"] = int(row["run"])
        row["time"] = float(row["time"])
        row["pi"] = float(row["pi"])
        check.ok(int(row["points"]) == POINTS, "section6: wrong point count")
        check.ok(row["time"] > 0, "section6: non-positive time")
        check.ok(abs(row["pi"] - PI_TRUE) <= 0.0015,
                 f"section6: implausible pi {row['pi']}")

    expected_s6 = RUNS * (2 * len(SECTION6_THREADS) + len(SECTION6_K))
    check.ok(len(section6) == expected_s6,
             f"section6_results.csv: {len(section6)} rows, expected {expected_s6}")

    s6 = group(section6, "approach", "threads", "k")
    batch_threads = (env.get("batch_threads")
                     or env.get("affinity_cpus")
                     or 2)
    check.ok(batch_threads in SECTION6_THREADS,
             f"environment: batch thread count {batch_threads} is not in the Section 6 sweep")
    for threads in SECTION6_THREADS:
        for approach in ("2", "3"):
            records = s6.get((approach, threads, 1000), [])
            check.ok(len(records) == RUNS,
                     f"section6 {approach} T={threads}: wrong run count")
        local = sorted(s6.get(("2", threads, 1000), []), key=lambda row: row["run"])
        shared = sorted(s6.get(("3", threads, 1000), []), key=lambda row: row["run"])
        for left, right in zip(local, shared):
            check.close(left["pi"], right["pi"], 1e-12,
                        f"section6 T={threads} run {left['run']}: pi mismatch")

    for frequency in SECTION6_K:
        records = s6.get(("batch", batch_threads, frequency), [])
        check.ok(len(records) == RUNS,
                 f"batch k={frequency}: wrong run count")
        reference = sorted(s6.get(("3", batch_threads, 1000), []),
                           key=lambda row: row["run"])
        for row in sorted(records, key=lambda row: row["run"]):
            match = next((item for item in reference if item["run"] == row["run"]), None)
            check.ok(match is not None,
                     f"batch k={frequency} run {row['run']}: no reference run")
            if match is not None:
                check.close(row["pi"], match["pi"], 1e-12,
                            f"batch k={frequency} run {row['run']}: pi mismatch")

    summary = read_csv(MEASUREMENTS / "section6_summary.csv")
    expected_summary = 2 * len(SECTION6_THREADS) + len(SECTION6_K)
    check.ok(len(summary) == expected_summary,
             f"section6_summary.csv: {len(summary)} rows, expected {expected_summary}")
    summary_index = {(row["approach"], int(row["threads"]), int(row["k"])): row
                     for row in summary}
    for (approach, threads, frequency), records in s6.items():
        row = summary_index.get((approach, threads, frequency))
        check.ok(row is not None,
                 f"section6_summary missing {approach} T={threads} k={frequency}")
        if row is None:
            continue
        times = [item["time"] for item in records]
        check.ok(int(row["runs"]) == len(records),
                 f"section6_summary {approach}/{threads}/{frequency}: run count")
        check.close(float(row["average_seconds"]), statistics.mean(times), 1e-12,
                    f"section6_summary {approach}/{threads}/{frequency}: mean")
        check.close(float(row["std_seconds"]), statistics.pstdev(times), 1e-12,
                    f"section6_summary {approach}/{threads}/{frequency}: std")
        check.close(float(row["mean_pi"]),
                    statistics.mean(item["pi"] for item in records), 1e-12,
                    f"section6_summary {approach}/{threads}/{frequency}: pi")

    # ------------------------------------------------------ high-thread probe
    probe = read_csv(MEASUREMENTS / "high_thread_probe.csv")
    for row in probe:
        row["threads"] = int(row["threads"])
        row["run"] = int(row["run"])
        row["time"] = float(row["time"])
        row["pi"] = float(row["pi"])
        check.ok(int(row["points"]) == POINTS, "probe: wrong point count")
        check.ok(row["time"] > 0, "probe: non-positive time")
        check.ok(abs(row["pi"] - PI_TRUE) <= 0.0015,
                 f"probe: implausible pi {row['pi']}")

    expected_probe = RUNS * 2 * len(PROBE_THREADS)
    check.ok(len(probe) == expected_probe,
             f"high_thread_probe.csv: {len(probe)} rows, expected {expected_probe}")
    probe_groups = group(probe, "approach", "threads")
    for threads in PROBE_THREADS:
        for approach in ("2", "3"):
            records = probe_groups.get((approach, threads), [])
            check.ok(len(records) == RUNS,
                     f"probe {approach} T={threads}: wrong run count")
            check.ok(sorted(item["run"] for item in records) == list(range(1, RUNS + 1)),
                     f"probe {approach} T={threads}: run numbers are not 1..{RUNS}")
        local = sorted(probe_groups.get(("2", threads), []), key=lambda row: row["run"])
        shared = sorted(probe_groups.get(("3", threads), []), key=lambda row: row["run"])
        for left, right in zip(local, shared):
            check.close(left["pi"], right["pi"], 1e-12,
                        f"probe T={threads} run {left['run']}: pi mismatch")

    probe_summary = read_csv(MEASUREMENTS / "high_thread_probe_summary.csv")
    check.ok(len(probe_summary) == 2 * len(PROBE_THREADS),
             f"high_thread_probe_summary.csv: {len(probe_summary)} rows, expected "
             f"{2 * len(PROBE_THREADS)}")
    probe_index = {(row["approach"], int(row["threads"])): row
                   for row in probe_summary}
    for (approach, threads), records in probe_groups.items():
        row = probe_index.get((approach, threads))
        check.ok(row is not None,
                 f"probe summary missing approach {approach} T={threads}")
        if row is None:
            continue
        times = [item["time"] for item in records]
        check.ok(int(row["runs"]) == len(records),
                 f"probe summary {approach}/{threads}: run count")
        check.close(float(row["average_seconds"]), statistics.mean(times), 1e-12,
                    f"probe summary {approach}/{threads}: mean")
        check.close(float(row["std_seconds"]), statistics.pstdev(times), 1e-12,
                    f"probe summary {approach}/{threads}: std")
        check.close(float(row["mean_pi"]),
                    statistics.mean(item["pi"] for item in records), 1e-12,
                    f"probe summary {approach}/{threads}: pi")
        check.close(float(row["speedup"]),
                    baseline_mean / statistics.mean(times), 1e-12,
                    f"probe summary {approach}/{threads}: speedup")

    # ------------------------------------------------------------- trends
    a2 = {item["threads"]: item for item in data["approach2_scaling"]}
    a3 = {item["threads"]: item for item in data["approach3_mutex_scaling"]}

    def mean_time(approach, threads, frequency=1000):
        records = s6.get((approach, threads, frequency), [])
        return statistics.mean(row["time"] for row in records) if records else None

    local_mean = {threads: mean_time("2", threads) for threads in SECTION6_THREADS}
    shared_mean = {threads: mean_time("3", threads) for threads in SECTION6_THREADS}
    batch_mean = {frequency: mean_time("batch", batch_threads, frequency)
                  for frequency in SECTION6_K}
    probe_mean = {key: statistics.mean(row["time"] for row in records)
                  for key, records in probe_groups.items() if records}

    complete = (set(a2) == set(PRIMARY_THREADS) and set(a3) == set(PRIMARY_THREADS)
                and None not in local_mean.values()
                and None not in shared_mean.values()
                and None not in batch_mean.values()
                and all(("2", threads) in probe_mean for threads in PROBE_THREADS)
                and all(("3", threads) in probe_mean for threads in PROBE_THREADS))
    check.ok(complete, "incomplete dataset (was --quick used?); trends not checked")

    if complete:
        check.trend(a2[1]["speedup"] >= 0.9 and a2[1]["speedup"] <= 1.15,
                    f"single-thread Approach 2 speedup is {a2[1]['speedup']:.2f}x, expected ~1x")
        check.trend(a2[2]["speedup"] >= 1.5,
                    f"2-thread speedup is only {a2[2]['speedup']:.2f}x; is the host pinned to 2 CPUs?")
        check.trend(max(item["speedup"] for item in a2.values()) >= 1.5,
                    "no Approach 2 configuration achieves 1.5x")
        check.trend(max(item["speedup"] for item in a3.values()) < 0.5,
                    "per-hit mutex is not clearly slower than the baseline")
        check.trend(a2[128]["mean_time"] <= 1.5 * a2[2]["mean_time"],
                    "128-thread time is more than 1.5x the 2-thread time; oversubscription is unusually severe")
        check.trend(local_mean[1] <= 1.2 * baseline_mean,
                    f"Section 6 T=1 local run ({local_mean[1]:.4f}s) is >20% slower than the baseline ({baseline_mean:.4f}s)")
        for threads in SECTION6_THREADS:
            if threads >= 2:
                check.trend(local_mean[threads] * 3 <= shared_mean[threads],
                            f"T={threads}: local accumulation is not at least 3x faster than the mutex")
        check.trend(batch_mean[1000] * 5 <= batch_mean[1],
                    "k=1000 is not at least 5x faster than per-hit batching")
        check.trend(probe_mean[("2", 256)] > a2[2]["mean_time"]
                    and probe_mean[("2", 512)] > a2[128]["mean_time"],
                    "the 256/512-thread probe does not show the expected decline")
        check.trend(probe_mean[("3", 512)] > 10 * probe_mean[("2", 512)],
                    "per-hit mutex is not clearly slower at 512 threads")

    # ---------------------------------------------------------------- links
    link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for relative in ("README.md", "1_source_code/README.md",
                     "4_analysis/analysis_report.md",
                     "5_best_practices/best_practices.md"):
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            check.ok((path.parent / local).exists(),
                     f"{relative}: broken link {target}")

    # ------------------------------------------------------------- summary
    return report(check, args.strict)


def report(check, strict):
    for warning in check.warnings:
        print(f"WARN: {warning}")
    if check.errors:
        for error in check.errors:
            print(f"FAIL: {error}")
        print(f"\n{len(check.errors)} check(s) failed, {check.passed} passed.")
        return 1
    if strict and check.warnings:
        print(f"\n{len(check.warnings)} warning(s) treated as errors (--strict).")
        return 1
    print(f"OK: {check.passed} checks passed"
          + (f", {len(check.warnings)} warning(s)." if check.warnings else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
