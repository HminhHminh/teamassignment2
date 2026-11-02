# Section 6: trade-off experiments

This section uses the team's existing `monte_carlo` program. Approach 2 (`-a 2`) supplies local accumulation, Approach 3 (`-a 3`) supplies the shared mutex, and the batch variant (`-a batch`) changes synchronization frequency. It does not replace the team's code for sections 3 and 4.

Run from the repository root on Ubuntu:

```bash
bash section6/run.sh 30000000 5 123456789
```

Arguments are points per configuration, repetitions, and master seed. The defaults match the team's existing 30-million-point, five-run benchmark. The script compiles the repository with `make` and writes outputs under `results/`.

| Experiment | Configurations | Output |
|---|---|---|
| 6.1 Synchronization frequency | `batch` at `k=1,10,100,1000`, fixed thread count equal to online logical CPUs | `results/section6_sync_frequency.svg` |
| 6.2 Thread scaling | Approach 2 at thread counts below, near, and above the CPU count | `results/section6_thread_scaling.svg` |
| 6.3 Local versus shared | Approaches 2 and 3 at identical thread counts and point count | `results/section6_local_vs_shared.svg` |

`results/section6_results.csv` contains each individual run. `results/section6_summary.csv` contains the average time for each configuration. The plot generator uses only Python's standard library.

## Results and discussion

The results below are from the current CSV files in `results/`. This run used Ubuntu with **4 online logical CPUs**, 30,000,000 points per configuration, 5 repetitions, and master seed `123456789`. The 4-CPU count is also reflected by the 4 threads used in experiment 6.1. Report the environment for this run separately from the earlier Section 4 benchmark, which used a different 2-vCPU setup.

### 6.1 Synchronization frequency

| Batch size `k` | Threads | Mean time (s) |
|---:|---:|---:|
| 1 | 4 | 1.1064 |
| 10 | 4 | 0.3441 |
| 100 | 4 | 0.0945 |
| 1000 | 4 | 0.1006 |

Increasing `k` from 1 to 100 greatly reduces time because workers acquire the mutex less often. The `k=1000` result is slightly slower than `k=100`, so the measurements do not show a perfectly decreasing trend; this difference may be run-to-run variation and should be described as measured.

### 6.2 Thread scaling with local accumulation

| Threads | Mean time (s) |
|---:|---:|
| 1 | 0.1570 |
| 2 | 0.0949 |
| 4 | 0.0829 |
| 5 | 0.0592 |
| 8 | 0.0535 |
| 16 | 0.0662 |
| 100 | 0.0559 |

Among the tested configurations, 8 threads had the lowest mean time. Increasing the count to 16 did not help, and 100 threads did not beat the 8-thread result. The measurements illustrate diminishing and non-monotonic returns as more threads compete for CPU time.

### 6.3 Local accumulation versus a shared mutex counter

| Threads | Local mean (s) | Shared mean (s) |
|---:|---:|---:|
| 1 | 0.1570 | 0.5942 |
| 2 | 0.0949 | 1.1966 |
| 4 | 0.0829 | 1.1702 |
| 5 | 0.0592 | 1.1205 |
| 8 | 0.0535 | 1.0359 |
| 16 | 0.0662 | 0.9049 |
| 100 | 0.0559 | 0.8386 |

The shared-counter approach was slower at every tested thread count. Each hit on the circle requires workers to contend for the same mutex-protected counter, while local accumulation lets each worker count independently and combines the totals afterward. The shared results also do not improve monotonically with thread count.

The raw measurements and averages are in `results/section6_results.csv` and `results/section6_summary.csv`; charts are `results/section6_sync_frequency.svg`, `results/section6_thread_scaling.svg`, and `results/section6_local_vs_shared.svg`. These averages are based on five runs, so small differences—especially the `k=100` versus `k=1000` result—should not be treated as a universal performance rule.

The C implementations create and initialize workers before timing. A start gate releases them after the timer starts, and each worker records its completion before the main thread joins it. Thus thread creation and joining are excluded while worker computation and mutex contention are included.

The C implementations create and initialize workers before timing. A start gate releases them after the timer starts, and each worker records its completion before the main thread joins it. Thus thread creation and joining are excluded while worker computation and mutex contention are included.
