# Week 3 — Multi-threading Best Practices via Monte Carlo π Estimation

Submission package for the group exercise. It contains every item required by
Section 7 of the specification, in the same order, plus the scripts and raw data
needed to reproduce the results.

## Deliverables index (specification Section 7)

| # | Required deliverable | Location |
|:--:|:--|:--|
| 1 | Source code (all approaches) | [`1_source_code/`](1_source_code/) — `src/`, `Makefile`, `build.bat`, build instructions |
| 2 | Performance measurements | [`2_measurements/`](2_measurements/) — raw CSV, JSON, summary tables, Section 6 data, environment metadata |
| 3 | Graphs (time, speedup, efficiency, throughput) | [`3_graphs/`](3_graphs/) — 7 PNG figures (4 primary + 3 trade-off) |
| 4 | Analysis and explanations | [`4_analysis/analysis_report.md`](4_analysis/analysis_report.md) — Sections 5.2 A–E and 6.1–6.3 |
| 5 | Identified best practices | [`5_best_practices/best_practices.md`](5_best_practices/best_practices.md) — 10 evidence-backed practices |

## Results at a glance

Primary benchmark: N = 30,000,000 points, 5 runs per configuration, pinned to
2 logical CPUs (`taskset -c 0-1`) on Ubuntu 24.04 / WSL2, GCC 13.3.0 `-O3`.

| Configuration | Mean time | Speedup | Throughput | Estimated π |
|:--|--:|--:|--:|--:|
| Approach 1 — single thread | 0.094655 s | 1.00× | 316.9 Mpts/s | 3.141434 |
| Approach 2 — local, 2 threads (best in primary sweep) | **0.0518 s** | **1.83×** | **579.3 Mpts/s** | 3.141525 |
| Approach 2 — local, 128 threads | 0.0572 s | 1.65× | 524.3 Mpts/s | 3.141816 |
| Approach 2 — local, 512 threads (probe) | 0.0636 s | 1.49× | 471.7 Mpts/s | 3.141471 |
| Approach 3 — mutex, 1 thread | 0.3727 s | 0.25× | 80.5 Mpts/s | 3.141434 |
| Approach 3 — mutex, 2 threads | 1.1868 s | 0.08× | 25.3 Mpts/s | 3.141525 |
| Batch sync — k = 1,000, 2 threads | **0.0499 s** | **1.90×** | 601.7 Mpts/s | 3.141525 |

Key findings:

- Local accumulation (map-reduce) reaches the 2-CPU plateau immediately and is
  **21.5× faster than the per-hit mutex at 2 threads** (up to 25.5× in the
  Section 6 sweep).
- Speedup saturates at **1.83× with 2 threads**, the CPU allocation. The full
  12-point sweep stays at 1.65–1.80× from 4 to 128 threads; 128 threads are
  about 10% slower than the peak. A supplementary probe at 256 and 512 threads
  falls to **1.54× and 1.49×** (19% below the peak), making the declining phase
  explicit.
- Per-hit locking is **3.97× slower than the baseline with one thread**; the
  critical section serializes ~23.6 million updates and costs at most ~11.8 ns
  per hit even uncontended.
- Batching the shared update every 1,000 iterations improves time by **21.5×**
  over per-hit locking and matches purely local accumulation, with π unchanged.
- All configurations estimate π within 0.000224 of the true value, consistent
  with the expected 1σ sampling error of ~0.00030 at N = 30M.

## Reproduce

Requirements: GCC with `-pthread`, Python 3.9+, and (for the figures)
`numpy` and `matplotlib`. On Linux, `taskset` (util-linux) is used to pin the
benchmark to 2 CPUs.

```bash
# From this package directory, in one step:
bash reproduce.sh

# Or manually:
make -C 1_source_code
python3 1_source_code/run_benchmarks.py --exe 1_source_code/monte_carlo --cpus 2
python3 1_source_code/plot_results.py
python3 verify.py
```

`run_benchmarks.py` needs only the Python standard library. `plot_results.py`
reads the JSON/CSV output and rewrites all figures and
`2_measurements/summary_tables.md`. `verify.py` checks structure, run counts,
CSV↔JSON consistency and correctness.

If matplotlib/numpy are unavailable, re-measure and verify without regenerating
the figures:

```bash
SKIP_PLOTS=1 bash reproduce.sh
```

On Windows use `build.bat`, then run the driver with `--no-affinity`; absolute
times will differ from the submitted Linux/2-CPU environment. `reproduce.bat`
wraps these steps.

The full campaign takes a few minutes because Approach 3 performs ~23.6 million
lock/unlock pairs per run. `--quick` is a smoke test only and is not
submittable.

## Directory structure

```
deliverables/
├── README.md                       <- this file
├── requirements.txt                plotting dependencies
├── reproduce.sh                    build + measure + plot + verify (POSIX)
├── reproduce.bat                   same steps on Windows
├── verify.py                       consistency and correctness checks
├── 1_source_code/
│   ├── README.md                   build/run instructions
│   ├── Makefile
│   ├── build.bat
│   ├── run_benchmarks.py           canonical benchmark driver
│   ├── plot_results.py             figures + summary tables
│   └── src/
│       ├── common.h
│       ├── approach1_single.c
│       ├── approach2_local.c
│       ├── approach3_mutex.c
│       ├── approach3_batch.c
│       └── main.c
├── 2_measurements/
│   ├── measurements.csv            all raw runs, Approaches 1–3
│   ├── benchmark_data.json         aggregated primary benchmark
│   ├── summary_tables.md           formatted tables
│   ├── section6_results.csv        Section 6 raw runs
│   ├── section6_summary.csv        Section 6 aggregate
│   ├── high_thread_probe.csv       256/512-thread supplementary raw runs
│   ├── high_thread_probe_summary.csv
│   └── environment.json            machine, compiler, affinity metadata
├── 3_graphs/
│   ├── execution_time_vs_threads.png
│   ├── speedup_vs_threads.png
│   ├── parallel_efficiency_vs_threads.png
│   ├── throughput_vs_threads.png
│   ├── section6_thread_scaling.png
│   ├── section6_local_vs_shared.png
│   └── section6_sync_frequency.png
├── 4_analysis/
│   └── analysis_report.md
└── 5_best_practices/
    └── best_practices.md
```

## Environment notes

- Primary environment: Ubuntu 24.04 on WSL2, kernel
  `6.6.87.2-microsoft-standard-WSL2`, host Intel Core i7-14650HX, 12 logical CPUs
  visible, **2 logical CPUs used** via `taskset -c 0-1`, GCC 13.3.0,
  `-O3 -pthread -Wall -Wextra -lm`.
- The benchmark is CPU-bound; the 2-CPU pin makes the scaling comparison
  meaningful. The SMT relationship of logical CPUs 0 and 1 was not verified.
- WSL2 shares the host with Windows, so run-to-run variation is 2.9% at the
  baseline and up to 9.1% in some parallel configurations. All conclusions are
  based on the full curve and differences well above that noise.
- Estimated π is compared with the true value 3.141592653589793.

## Provenance

All measurements, tables and figures in this package were regenerated on
**2026-11-03** from the same source revision and the same timing methodology
(start gate; thread creation/join excluded). Earlier drafts used a VMware
2-vCPU environment and a separate Windows experiment that timed
`pthread_create → pthread_join`; those datasets are superseded and are no longer
included, so every number in the package belongs to one consistent experiment.

## Submission details

Fill in before uploading:

| Field | Value |
|:--|:--|
| Course | CO2018 — Operating Systems |
| Group | |
| Members | |
