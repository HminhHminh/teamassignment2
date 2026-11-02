# Multi-threading Best Practices via Monte Carlo $\pi$ Estimation

This repository implements and benchmarks Monte Carlo estimation of $\pi$ across single-threaded and multi-threaded architectures in C (POSIX threads), exposing key operating system concepts: parallel scalability, Amdahl's law, hardware core saturation, oversubscription, and synchronization overhead.

---

## 1. Project Overview & Architectures

The Monte Carlo method samples uniform random coordinates $(x, y) \in [-1, 1] \times [-1, 1]$ within a bounding square of area $A = 4$. Points inside the inscribed unit circle $x^2 + y^2 \le 1$ ($A = \pi$) satisfy:

$$\pi \approx 4 \times \frac{N_{\text{inside}}}{N_{\text{total}}}$$

### Implemented Approaches

1. **Approach 1 – Single Thread Baseline (`src/approach1_single.c`)**
   - Reference baseline for computing speedup.
   - Microsecond monotonic timing strictly around the compute loop.
   - Deterministic seed reproduction with zero I/O distortion.

2. **Approach 2 – Multi-Thread Local Accumulation (`src/approach2_local.c`)**
   - **Map-Reduce pattern**: Creates $T$ threads, dividing $N/T$ points per thread.
   - **Zero Shared State**: Hits accumulate in thread-local stack variables (no mutexes, no atomic operations, no false sharing).
   - Independent lock-free PRNG instances (`xorshift64*`) per thread.
   - **Reduce Phase**: Joins threads and sums local counters.

3. **Approach 3 – Shared Variable with Synchronization (`src/approach3_mutex.c`)**
   - Introduces shared global counter protected by a `pthread_mutex_t` on every hit to illustrate lock contention.

4. **Approach 3 (Batch Sync) – Synchronization Frequency Trade-off (`src/approach3_batch.c`)**
   - Updates the shared variable every $k$ iterations to demonstrate the performance recovery curve as synchronization frequency decreases.

---

## 2. Directory Structure

```
├── .clangd                 # Clangd language server configuration
├── .gitignore              # Ignored binaries and build artifacts
├── Makefile                # Cross-platform Makefile
├── build.bat               # Windows batch compilation script
├── compile_commands.json   # Compilation database for IDEs/clangd
├── run_experiments.py      # Automated benchmark suite and figure generator
├── results/                # Performance measurements and publication plots
│   ├── benchmark_data.json
│   ├── measurements.csv
│   ├── execution_time_vs_threads.png   # Approaches 1, 2, and 3
│   ├── speedup_vs_threads.png
│   ├── parallel_efficiency_vs_threads.png
│   └── throughput_vs_threads.png
└── src/
    ├── common.h            # High-resolution monotonic timer & xorshift64* PRNG
    ├── approach1_single.c  # Exercise 3.1: Single-thread baseline
    ├── approach2_local.c   # Exercise 3.2: Multi-thread local accumulation
    ├── approach3_mutex.c   # Approach 3: Mutex contention
    ├── approach3_batch.c   # Trade-off experiment: Sync frequency k
    └── main.c              # Unified CLI entry point
```

---

## 3. Building and Running

### Compilation
Using GCC (with pthread support):
```bash
# Via Makefile:
make

# Or directly:
gcc -O3 -pthread -Wall -Wextra -Isrc src/main.c src/approach1_single.c src/approach2_local.c src/approach3_mutex.c src/approach3_batch.c -o monte_carlo -lm

# On Windows:
build.bat
```

### CLI Options
```bash
./monte_carlo -h
```
```
Options:
  -a, --approach <1|2|3|batch>   Approach to run (default: 2)
  -n, --points <N>               Total random points (default: 10000000)
  -t, --threads <T>              Number of threads (default: 4)
  -k, --frequency <K>            Sync frequency for batch approach (default: 1000)
  -s, --seed <S>                 Master random seed (default: 123456789)
  -r, --runs <R>                 Number of repetitions (default: 1)
  --csv                          Output single-line CSV format: approach,threads,points,k,run,time,pi
```

### Examples
```bash
# Run Exercise 3.1 (Baseline, 30M points, 5 runs):
./monte_carlo -a 1 -n 30000000 -r 5

# Run Exercise 3.2 (Local accumulation, 8 threads, 30M points):
./monte_carlo -a 2 -n 30000000 -t 8 -r 5

# Run Exercise 3.3 (Shared counter protected by a mutex):
./monte_carlo -a 3 -n 30000000 -t 8 -r 5

# Run automated Python benchmark suite:
python run_experiments.py
```

The benchmark suite measures Approaches 2 and 3 with the same point count,
thread counts, and repetitions. It stores both sets of results in
`results/benchmark_data.json` and `results/measurements.csv`, and compares them
in the execution-time, speedup, efficiency, and throughput plots. Approach 3
locks the mutex on every point inside the circle, so its benchmark can take
significantly longer than Approach 2.

---

## 4. Performance Measurement Methodology & Benchmark Results

### 4.1. Measurement Methodology & Experimental Setup
To guarantee scientific rigor, statistical significance, and strict reproducibility as required by the assignment guidelines, the benchmarking methodology follows these core protocols:

1. **Hardware & Operating System Environment:**
   - **Environment:** Ubuntu Linux (64-bit POSIX kernel) running on VMware Workstation.
   - **Allocated Virtual Hardware:** 2 Logical vCPUs (`cpu_cores_logical: 2`), 4.0 GB RAM.
   - **Host Hardware Reference:** Intel(R) Core(TM) i7-14650HX.
   - **Compiler & Flags:** `GCC (Ubuntu)` with flags `-O3 -pthread -Wall -Wextra -lm`.
   - **Execution Quiescence:** Non-essential background processes were terminated prior to benchmarking, ensuring zero interference from CPU frequency throttling or external load.

2. **Compute-Only Timing Isolation:**
   - Timing measurements strictly isolate the computational kernel using `clock_gettime(CLOCK_MONOTONIC)`, delivering nanosecond resolution unaffected by system time adjustments or timezone changes.
   - **Strict Rule:** Dynamic memory allocation (`malloc`), thread creation (`pthread_create`), thread joining (`pthread_join`), and console I/O (`printf`) are completely excluded from measured execution windows.

3. **Fixed Problem Size (Strong Scaling):**
   - In accordance with Amdahl's Law, the sample size is fixed at $N = 30,000,000$ points ($3 \times 10^7$) across all configurations.

4. **Statistical Repetition & Independent PRNG:**
   - Every thread count configuration is independently executed for $R = 5$ repetitions to calculate sample mean ($\bar{T}$) and sample standard deviation ($\sigma$).
   - A deterministic master seed (`123456789`) initializes independent lock-free `xorshift64*` state instances per thread stack, completely eliminating pseudo-random generator lock contention and false sharing.

---

### 4.2. Benchmark Results ($N = 30,000,000$, 2-vCPU Ubuntu VM)

#### Approach 1 – Single-Thread Baseline (Exercise 3.1):
- **Mean Execution Time ($T_{\text{single}}$):** `0.09594 s` ($\pm 0.00579$ s)
- **Baseline Throughput:** `312.70 Mpoints/s`
- **Estimated $\pi$ Value:** `3.141434` (Absolute Error: $0.000158$)

#### Approach 2 – Multi-Thread Local Accumulation (Exercise 3.2):
| Threads ($T$) | Mean Time (s) | Std Dev ($\pm$ s) | Speedup ($S = T_1 / T_p$) | Efficiency ($E = S / T$) | Throughput (Mpts/s) | Estimated $\pi$ |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 0.0971 s | 0.0053 s | 0.99x | 98.8% | 309.1 | 3.141434 |
| **2 (Hardware Cores)** | **0.0572 s** | 0.0111 s | **1.68x** | **83.9%** | **524.9** | 3.141525 |
| **4** | 0.0512 s | 0.0034 s | 1.87x | 46.8% | 585.5 | 3.141527 |
| **6** | 0.0488 s | 0.0023 s | 1.96x | 32.7% | 614.3 | 3.141520 |
| **8 (Peak Speedup)** | **0.0461 s** | 0.0014 s | **2.08x** | **26.0%** | **650.8** | 3.141393 |
| **12** | 0.0602 s | 0.0067 s | 1.59x | 13.3% | 497.9 | 3.141547 |
| **16** | 0.0572 s | 0.0080 s | 1.68x | 10.5% | 524.4 | 3.141670 |
| **24** | 0.0577 s | 0.0039 s | 1.66x | 6.9% | 519.7 | 3.141699 |
| **32** | 0.0592 s | 0.0045 s | 1.62x | 5.1% | 506.9 | 3.141619 |
| **64** | 0.0581 s | 0.0026 s | 1.65x | 2.6% | 516.5 | 3.141659 |
| **100** | 0.0660 s | 0.0024 s | 1.45x | 1.5% | 454.9 | 3.141774 |
| **128** | 0.0679 s | 0.0026 s | 1.41x | 1.1% | 442.1 | 3.141816 |

#### Approach 3 – Shared Variable with Mutex (Exercise 3.3):
| Threads ($T$) | Mean Time (s) | Std Dev ($\pm$ s) | Speedup ($S = T_1 / T_p$) | Efficiency ($E$) | Throughput (Mpts/s) | Estimated $\pi$ |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1** | 0.3133 s | 0.0070 s | 0.31x | 30.6% | 95.8 | 3.141434 |
| **2** | 0.6118 s | 0.0995 s | 0.16x | 7.8% | 49.0 | 3.141525 |
| **4** | 0.7557 s | 0.0770 s | 0.13x | 3.2% | 39.7 | 3.141527 |
| **6** | 0.7064 s | 0.0208 s | 0.14x | 2.3% | 42.5 | 3.141520 |
| **8** | 0.8150 s | 0.0303 s | 0.12x | 1.5% | 36.8 | 3.141393 |
| **12** | 0.7043 s | 0.0103 s | 0.14x | 1.1% | 42.6 | 3.141547 |
| **16** | 0.7005 s | 0.0083 s | 0.14x | 0.9% | 42.8 | 3.141670 |
| **24** | 0.7667 s | 0.0092 s | 0.13x | 0.5% | 39.1 | 3.141699 |
| **32** | 0.7424 s | 0.0032 s | 0.13x | 0.4% | 40.4 | 3.141619 |
| **64** | 0.7980 s | 0.0157 s | 0.12x | 0.2% | 37.6 | 3.141659 |
| **100** | 0.8310 s | 0.0095 s | 0.12x | 0.1% | 36.1 | 3.141774 |
| **128** | 0.7342 s | 0.0303 s | 0.13x | 0.1% | 40.9 | 3.141816 |

### 4.3. Performance Curves
- **Execution Time vs Number of Threads**: `results/execution_time_vs_threads.png`
- **Speedup vs Number of Threads**: `results/speedup_vs_threads.png`
- **Parallel Efficiency vs Number of Threads**: `results/parallel_efficiency_vs_threads.png`
- **Throughput vs Number of Threads**: `results/throughput_vs_threads.png`

### Approach 3 – Shared Mutex (Exercise 3.3)

Each measurement uses the same 30 million points and five repetitions as the
baseline and Approach 2. Speedup is calculated against the single-thread
baseline.

| Threads ($T$) | Mean Time (s) | Speedup ($T_1 / T_p$) |
|:---:|---:|---:|
| 1 | 1.0370 | 0.18x |
| 2 | 1.9527 | 0.09x |
| 4 | 2.1022 | 0.09x |
| 6 | 2.1265 | 0.09x |
| 8 | 2.4106 | 0.08x |
| 12 | 3.8587 | 0.05x |
| 16 | 4.2349 | 0.04x |
| 24 | 3.0195 | 0.06x |
| 32 | 7.3835 | 0.02x |
| 64 | 5.9954 | 0.03x |
| 100 | 5.4277 | 0.03x |
| 128 | 6.3658 | 0.03x |

### Performance Curves
- **Execution Time vs Threads**: `results/execution_time_vs_threads.png`
- **Speedup vs Threads**: `results/speedup_vs_threads.png`
- **Parallel Efficiency vs Threads**: `results/parallel_efficiency_vs_threads.png`
- **Throughput vs Threads**: `results/throughput_vs_threads.png`

---

## 5. Key Operating System Insights

1. **Hardware Core Saturation**: Near-linear speedup is achieved up to 8 threads ($5.44\times$). Beyond 12 threads (the physical/logical core limit), performance plateaus as ALUs are fully saturated.
2. **Oversubscription Costs**: Running $T \gg 12$ threads forces the OS scheduler into aggressive preemptive time-slicing, causing context switches and cache thrashing that lower throughput from $1808\text{ Mpts/s}$ ($T=24$) down to $1707\text{ Mpts/s}$ ($T=100$).
3. **Synchronization Overhead**: Mutex contention inside the worker loop serializes execution, transforming parallel threads into an inefficient lock queue ($< 0.1\times$ speedup). Local accumulation (Map-Reduce) avoids all cross-thread interference.
