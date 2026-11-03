# Week 3 — Multi-threading Best Practices via Monte Carlo π Estimation

Submission package for the group exercise. It contains every item required by
Section 7 of the specification, in the same order.

## Deliverables index (specification Section 7)

| # | Required deliverable | Location |
|:--:|:--|:--|
| 1 | Source code (all approaches) | [`1_source_code/`](1_source_code/) — `src/`, `Makefile`, `build.bat`, build instructions |
| 2 | Performance measurements | [`2_measurements/`](2_measurements/) — raw CSV, JSON, summary tables, sync-frequency experiment |
| 3 | Graphs (time, speedup, efficiency, throughput) | [`3_graphs/`](3_graphs/) — 5 PNG figures |
| 4 | Analysis and explanations | [`4_analysis/analysis_report.md`](4_analysis/analysis_report.md) — Sections 5.2 A–E and 6.1–6.3 |
| 5 | Identified best practices | [`5_best_practices/best_practices.md`](5_best_practices/best_practices.md) — 10 evidence-backed practices |

## Results at a glance

Primary benchmark: N = 30,000,000 points, 5 runs per configuration, Ubuntu VM
with 2 logical vCPUs.

| Configuration | Mean time | Speedup | Throughput | Estimated π |
|:--|--:|--:|--:|--:|
| Approach 1 — single thread | 0.09594 s | 1.00× | 312.7 Mpts/s | 3.141434 |
| Approach 2 — local, 2 threads | 0.0572 s | 1.68× | 524.9 Mpts/s | 3.141525 |
| Approach 2 — local, 8 threads (best) | **0.0461 s** | **2.08×** | **650.8 Mpts/s** | 3.141393 |
| Approach 3 — mutex, 1 thread (best) | 0.3133 s | 0.31× | 95.8 Mpts/s | 3.141434 |
| Approach 3 — mutex, 8 threads | 0.8150 s | 0.12× | 36.8 Mpts/s | 3.141393 |

Key findings:

- Local accumulation (map-reduce) scales up to the available cores and is
  **17.7× faster than the per-hit mutex at 8 threads**.
- Speedup saturates at ~2× (the 2-vCPU limit); 12–128 threads are 30–47% slower
  than the 8-thread result due to oversubscription.
- Per-hit locking is 3.3× slower than the baseline even with one thread; the
  critical section serializes ~23.6 million updates.
- Batching the shared update every 1,000 iterations improves time by **35.8×**
  over per-hit locking while keeping π = 3.141393 exactly.

## Directory structure

```
deliverables/
├── README.md                       <- this file
├── 1_source_code/
│   ├── README.md                   build/run instructions
│   ├── Makefile
│   ├── build.bat
│   ├── run_experiments.py          primary benchmark driver
│   └── src/
│       ├── common.h
│       ├── approach1_single.c
│       ├── approach2_local.c
│       ├── approach3_mutex.c
│       ├── approach3_batch.c
│       └── main.c
├── 2_measurements/
│   ├── measurements.csv            all raw runs, Approaches 1-3
│   ├── benchmark_data.json         aggregated primary benchmark
│   ├── summary_tables.md           formatted tables
│   ├── sync_frequency_runs.csv     Section 6.1 raw runs
│   ├── sync_frequency_summary.csv  Section 6.1 aggregate
│   ├── sync_frequency_metadata.json
│   └── run_sync_frequency.py       Section 6.1 experiment script
├── 3_graphs/
│   ├── execution_time_vs_threads.png
│   ├── speedup_vs_threads.png
│   ├── parallel_efficiency_vs_threads.png
│   ├── throughput_vs_threads.png
│   └── sync_frequency_vs_time.png
├── 4_analysis/
│   └── analysis_report.md
└── 5_best_practices/
    └── best_practices.md
```

## Reproduce

```bash
# 1. Build (Linux / MinGW)
cd deliverables/1_source_code
make

# 2. Regenerate the primary benchmark (takes a few minutes).
#    Outputs are written to 1_source_code/results/; copy them into
#    2_measurements/ and 3_graphs/ to replace the packaged data.
python run_experiments.py

# 3. Regenerate the Section 6.1 trade-off experiment
cd ../2_measurements
python run_sync_frequency.py --exe ../1_source_code/monte_carlo
```

On Windows use `build.bat` and run
`python run_sync_frequency.py --exe ..\1_source_code\monte_carlo.exe`.

## Environment notes

- The primary benchmark was collected on an Ubuntu 64-bit VM with **2 logical
  vCPUs** and 4 GiB RAM (host: Intel Core i7-14650HX), compiled with
  `gcc -O3 -pthread -Wall -Wextra -lm`.
- The Section 6.1 synchronization-frequency experiment was collected on a
  native Windows 11 machine with **12 logical CPUs**. Its timings are compared
  only within that experiment, not against the VM tables.
- Estimated π is reported with the true value 3.141592653589793.

## Submission details

Fill in before uploading:

| Field | Value |
|:--|:--|
| Course | CO2018 — Operating Systems |
| Group | |
| Members | |
