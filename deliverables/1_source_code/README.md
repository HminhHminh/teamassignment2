# Source Code

All approaches required by the specification are implemented in C using POSIX
threads.

## Files

| File | Purpose |
|:--|:--|
| `src/common.h` | Monotonic timer, `xorshift64*` PRNG, per-thread seed derivation |
| `src/approach1_single.c` | Approach 1: single-thread baseline |
| `src/approach2_local.c` | Approach 2: local accumulation + final reduction (map-reduce) |
| `src/approach3_mutex.c` | Approach 3: global counter protected by a mutex on every hit |
| `src/approach3_batch.c` | Trade-off: shared counter updated every *k* iterations |
| `src/main.c` | Command-line entry point, repetition handling, summary/CSV output |
| `Makefile` | Linux / MinGW build |
| `build.bat` | Windows build |
| `run_experiments.py` | Original benchmark driver for Approaches 1–3 and plots |

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

# Local accumulation, 8 threads, 30M points, 5 runs
./monte_carlo -a 2 -n 30000000 -t 8 -r 5

# Per-hit mutex, 8 threads, 30M points, 5 runs
./monte_carlo -a 3 -n 30000000 -t 8 -r 5

# Batch synchronization every 1000 iterations
./monte_carlo -a batch -n 30000000 -t 8 -k 1000 -r 5
```

## Implementation notes

- Timing uses `CLOCK_MONOTONIC`. For parallel approaches it spans
  `pthread_create` through `pthread_join`; allocation, seed setup, mutex
  init/destroy and output are outside the timed region.
- The master seed is fixed (`123456789`); each thread derives an independent
  `xorshift64*` state from it and its thread id. Repetition *r* uses the
  deterministic seed `master + 99991r`, so runs are reproducible and no PRNG lock
  is needed; different repetitions differ only by sampling noise.
- Approach 2 keeps the counter on the thread stack and writes it once at the
  end, avoiding false sharing in the sampling loop.
- Approach 3 locks a single global counter on every point inside the circle
  (~78.5% of samples).
- Approach 3 batch flushes any partial batch after the loop; omitting that flush
  would undercount.

The compiled binary is intentionally not included in this submission package.
Build it locally with the commands above.
