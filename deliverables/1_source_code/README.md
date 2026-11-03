# Source Code

All approaches required by the specification are implemented in C using POSIX
threads. The package ships source only; build the binary locally.

## Files

| File | Purpose |
|:--|:--|
| `src/common.h` | Monotonic timer, `StartGate`, `xorshift64*` PRNG, per-thread seed derivation |
| `src/approach1_single.c` | Approach 1: single-thread baseline |
| `src/approach2_local.c` | Approach 2: local accumulation + final reduction (map-reduce) |
| `src/approach3_mutex.c` | Approach 3: global counter protected by a mutex on every hit |
| `src/approach3_batch.c` | Trade-off: shared counter updated every *k* iterations |
| `src/main.c` | Command-line entry point, repetition handling, summary/CSV output |
| `Makefile` | Linux / MinGW build |
| `build.bat` | Windows build |
| `run_benchmarks.py` | Canonical benchmark driver (standard library only) |
| `plot_results.py` | Builds all figures and `2_measurements/summary_tables.md` (needs numpy + matplotlib) |

## Build

Requirements: GCC with POSIX threads (`-pthread`) and `libm`.

```bash
# Linux / macOS / MinGW shell
make

# Windows
build.bat

# Direct command
gcc -O3 -pthread -Wall -Wextra -Isrc \
    src/main.c src/approach1_single.c src/approach2_local.c \
    src/approach3_mutex.c src/approach3_batch.c \
    -o monte_carlo -lm
```

## Run

```bash
./monte_carlo -h
```

```
-a, --approach <1|2|3|batch>   Approach to run (default: 2)
-n, --points <N>               Total random points (default: 10000000)
-t, --threads <T>              Number of threads (default: 4)
-k, --frequency <K>            Sync frequency for batch approach (default: 1000)
-s, --seed <S>                 Master random seed (default: 123456789)
-r, --runs <R>                 Number of repetitions (default: 1)
--csv                          One-line CSV: approach,threads,points,k,run,time,pi
-h, --help                     Usage
```

Examples used for the report:

```bash
# Baseline, 30M points, 5 runs
./monte_carlo -a 1 -n 30000000 -r 5

# Local accumulation, 2 threads, 30M points, 5 runs
./monte_carlo -a 2 -n 30000000 -t 2 -r 5

# Per-hit mutex, 2 threads, 30M points, 5 runs
./monte_carlo -a 3 -n 30000000 -t 2 -r 5

# Batch synchronization every 1000 iterations
./monte_carlo -a batch -n 30000000 -t 2 -k 1000 -r 5
```

## Automated benchmark

From the package root, after building:

```bash
python3 1_source_code/run_benchmarks.py --exe 1_source_code/monte_carlo --cpus 2
python3 1_source_code/plot_results.py
```

`run_benchmarks.py` uses only the Python standard library. It pins the process to
the first `--cpus` logical CPUs with `taskset` on Linux; use `--no-affinity` to
disable pinning. It rewrites the CSV/JSON files in `2_measurements/`, including
the supplementary 256/512-thread probe. `plot_results.py` requires `numpy` and
`matplotlib` (see `requirements.txt` at the package root) and rewrites the seven
figures and `summary_tables.md`.

## Implementation notes

- Timing uses `clock_gettime(CLOCK_MONOTONIC)`.
- For Approaches 2, 3 and the batch variant, all workers are created first and
  wait on a `StartGate` (mutex + condition variable). Releasing the gate records
  `t_start` and wakes every worker; each worker records `finished_at`
  immediately after its loop, and elapsed time is
  `max(finished_at) - t_start`. Thread creation/join, allocation, seed setup,
  mutex init/destroy, the final reduction and all output are outside the timed
  region. Approach 1 times only its sampling loop.
- The master seed is fixed (`123456789`); each thread derives an independent
  `xorshift64*` state from the master seed and its thread id. Repetition *r* uses
  the deterministic seed `master + 99991r`, so runs are reproducible and no PRNG
  lock is needed; different repetitions differ only by sampling noise.
- Approach 2 keeps the counter on the thread stack and writes it once at the
  end, avoiding false sharing in the sampling loop.
- Approach 3 locks a single global counter on every point inside the circle
  (~78.5% of samples).
- The batch variant flushes any partial batch after the loop; omitting that flush
  would undercount.

The compiled binary is intentionally not included in this submission package.
Build it locally with the commands above.
