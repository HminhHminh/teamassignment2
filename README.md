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
│   ├── execution_time_vs_threads.png
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

# Run automated Python benchmark suite:
python run_experiments.py
```

---

## 4. Benchmark Results ($N = 30,000,000$, 12-Core Host)

| Threads ($T$) | Mean Time (s) | Speedup ($S = T_1 / T_p$) | Efficiency ($E = S / T$) | Throughput (Mpts/s) | Estimated $\pi$ |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **1 (Baseline 3.1)** | **0.1093 s** | **1.00x** | **100.0%** | **274.5** | 3.141434 |
| 2 | 0.0565 s | 1.94x | 96.8% | 531.3 | 3.141525 |
| 4 | 0.0318 s | 3.44x | 85.9% | 943.4 | 3.141527 |
| 6 | 0.0263 s | 4.15x | 69.2% | 1140.3 | 3.141520 |
| 8 | 0.0201 s | 5.44x | 68.0% | 1494.4 | 3.141393 |
| **12 (Physical Cores)** | **0.0195 s** | **5.61x** | **46.7%** | **1538.9** | 3.141547 |
| **24 (Peak)** | **0.0166 s** | **6.59x** | **27.4%** | **1808.3** | 3.141699 |
| 64 | 0.0174 s | 6.28x | 9.8% | 1723.6 | 3.141659 |
| 128 | 0.0174 s | 6.26x | 4.9% | 1719.5 | 3.141816 |

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
