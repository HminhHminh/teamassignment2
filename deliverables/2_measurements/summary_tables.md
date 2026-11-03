# Performance Measurements

All values are means over 5 independent runs. Raw per-run data is in
`measurements.csv` and `benchmark_data.json`.

- Problem size: **N = 30,000,000** points (fixed for every configuration)
- Master seed: `123456789`; each run derives a deterministic successor seed
- Speedup: `S(T) = T_single / T_parallel`, where `T_single = 0.09594 s`
- Parallel efficiency: `E(T) = S(T) / T`
- Throughput: `N / T_parallel` (million points per second)

---

## 1. Primary benchmark — Ubuntu VM, 2 logical vCPUs

### Approach 1 — Single-thread baseline (Exercise 3.1)

| Metric | Value |
|:--|--:|
| Mean execution time | **0.09594 s** |
| Standard deviation | ± 0.00579 s |
| Throughput | 312.70 Mpoints/s |
| Estimated π | 3.141434 (absolute error 0.000158) |

### Approach 2 — Local accumulation (Exercise 3.2)

| Threads | Mean time (s) | Std dev (s) | Speedup | Efficiency (%) | Throughput (Mpts/s) | Estimated π |
|:--:|--:|--:|--:|--:|--:|--:|
| 1 | 0.0971 | 0.0053 | 0.99× | 98.8 | 309.1 | 3.141434 |
| 2 | 0.0572 | 0.0111 | 1.68× | 83.9 | 524.9 | 3.141525 |
| 4 | 0.0512 | 0.0034 | 1.87× | 46.8 | 585.5 | 3.141527 |
| 6 | 0.0488 | 0.0023 | 1.96× | 32.7 | 614.3 | 3.141520 |
| **8** | **0.0461** | 0.0014 | **2.08×** | 26.0 | **650.8** | 3.141393 |
| 12 | 0.0602 | 0.0067 | 1.59× | 13.3 | 497.9 | 3.141547 |
| 16 | 0.0572 | 0.0080 | 1.68× | 10.5 | 524.4 | 3.141670 |
| 24 | 0.0577 | 0.0039 | 1.66× | 6.9 | 519.7 | 3.141699 |
| 32 | 0.0592 | 0.0045 | 1.62× | 5.1 | 506.9 | 3.141619 |
| 64 | 0.0581 | 0.0026 | 1.65× | 2.6 | 516.5 | 3.141659 |
| 100 | 0.0660 | 0.0024 | 1.45× | 1.5 | 454.9 | 3.141774 |
| 128 | 0.0679 | 0.0026 | 1.41× | 1.1 | 442.1 | 3.141816 |

### Approach 3 — Shared variable with per-hit mutex (Exercise 3.3)

| Threads | Mean time (s) | Std dev (s) | Speedup | Efficiency (%) | Throughput (Mpts/s) | Estimated π |
|:--:|--:|--:|--:|--:|--:|--:|
| 1 | 0.3133 | 0.0070 | 0.31× | 30.6 | 95.8 | 3.141434 |
| 2 | 0.6118 | 0.0995 | 0.16× | 7.8 | 49.0 | 3.141525 |
| 4 | 0.7557 | 0.0770 | 0.13× | 3.2 | 39.7 | 3.141527 |
| 6 | 0.7064 | 0.0208 | 0.14× | 2.3 | 42.5 | 3.141520 |
| 8 | 0.8150 | 0.0303 | 0.12× | 1.5 | 36.8 | 3.141393 |
| 12 | 0.7043 | 0.0103 | 0.14× | 1.1 | 42.6 | 3.141547 |
| 16 | 0.7005 | 0.0083 | 0.14× | 0.9 | 42.8 | 3.141670 |
| 24 | 0.7667 | 0.0092 | 0.13× | 0.5 | 39.1 | 3.141699 |
| 32 | 0.7424 | 0.0032 | 0.13× | 0.4 | 40.4 | 3.141619 |
| 64 | 0.7980 | 0.0157 | 0.12× | 0.2 | 37.6 | 3.141659 |
| 100 | 0.8310 | 0.0095 | 0.12× | 0.1 | 36.1 | 3.141774 |
| 128 | 0.7342 | 0.0303 | 0.13× | 0.1 | 40.9 | 3.141816 |

---

## 2. Supplementary experiment — synchronization frequency (Section 6.1)

**Environment:** Windows 11 host, Intel Core i7-14650HX, **12 logical CPUs**,
N = 30,000,000, T = 8, 5 runs per configuration. This experiment was run on a
different machine from the primary benchmark, so compare values only *within*
this table.

Reference points at the same N and T:

| Configuration | Mean time (s) | Speedup vs single |
|:--|--:|--:|
| Single thread (Approach 1) | 0.0922 | 1.00× |
| Local accumulation (Approach 2) | **0.0195** | **4.73×** |
| Per-hit mutex (Approach 3) | 0.9705 | 0.095× |

Batch synchronization every *k* iterations (Approach 3, batch variant):

| k | Mean time (s) | Std dev (s) | Speedup vs single | Throughput (Mpts/s) |
|--:|--:|--:|--:|--:|
| 1 | 1.2252 | 0.0435 | 0.08× | 24.5 |
| 10 | 0.3964 | 0.0572 | 0.23× | 75.7 |
| 100 | 0.0770 | 0.0126 | 1.20× | 389.4 |
| **1,000** | **0.0271** | 0.0064 | **3.40×** | **1108.2** |
| 10,000 | 0.0342 | 0.0047 | 2.69× | 876.2 |
| 100,000 | 0.0392 | 0.0055 | 2.35× | 764.6 |
| 1,000,000 | 0.0379 | 0.0095 | 2.43× | 791.8 |

Estimated π is **3.141393** for every configuration: batching changes only the
update frequency, not the count, so correctness is preserved.

Raw files:
- `sync_frequency_runs.csv` — every run
- `sync_frequency_summary.csv` — aggregated table
- `sync_frequency_metadata.json` — host description and reference timings
- `run_sync_frequency.py` — reproducible experiment script
