# Identified Best Practices

Derived from the measurements in [`summary_tables.md`](../2_measurements/summary_tables.md)
and the analysis in [`analysis_report.md`](../4_analysis/analysis_report.md).
Every practice cites the evidence collected in this exercise, followed by the
recommended pattern and the anti-pattern to avoid.

Environment for all numbers: N = 30,000,000, 5 runs per configuration, GCC 13.3.0
`-O3 -pthread`, Ubuntu 24.04 on WSL2, pinned to **2 logical CPUs**
(`taskset -c 0-1`). Baseline: 0.094655 s, 316.9 Mpoints/s.

---

## 1. Accumulate locally, reduce once (map-reduce)

**Practice.** Give every thread a private counter; after `pthread_join`, sum the
partial counters in the main thread.

**Evidence.** At 2 threads, local accumulation took 0.0500 s versus 1.0771 s for
a per-hit mutex — **21.5× faster**; at 8 threads it was **25.5× faster**
(0.0515 s vs 1.3123 s). Both designs produced the identical π estimate for each
thread count. The reduce phase is O(T) and is outside the timed region; its cost
is negligible.

**Avoid.** Incrementing a global counter inside the sampling loop, even under a
mutex or an atomic. It turns an embarrassingly parallel loop into a serial one.

---

## 2. Keep shared mutable state out of the hot loop

**Practice.** If a shared update is unavoidable, make it **rare** and batch it:
maintain a local subtotal and publish it every *k* iterations, then flush the
remainder after the loop.

**Evidence.** Reducing the update frequency from every iteration to every 1,000
iterations cut the time from 1.0744 s to 0.0499 s (**21.5×**) at T = 2, and the
result stayed exactly π = 3.141524640. At *k* = 1,000 the batch design matches
purely local accumulation (0.0500 s): synchronization is no longer the
bottleneck.

**Avoid.** Locking once per element or per hit "for simplicity". It is the
slowest design measured in this lab, by a factor of roughly 20 even at two
threads.

---

## 3. Batch cheaply: count down or process blocks, do not modulo every iteration

**Practice.** Prefer a counter that triggers an update less often than the loop
body:

```c
if (++since_update == k) { publish(local); since_update = 0; }
```

or process the input in blocks of *k* and publish after each block.

**Evidence.** The implemented batch variant uses `(i + 1) % k` with a runtime
divisor, so GCC emits an integer division in the loop. On this CPU the
out-of-order pipeline hides it behind the serial PRNG dependency, and the
*k* = 1,000 result (0.0499 s, 0.0005 s spread) is statistically identical to
local accumulation without any division (0.0500 s). That is a property of this
micro-architecture, not a guarantee: the division is still in the instruction
stream and may cost on in-order or narrower cores. A countdown or block loop
removes the risk at no cost.

**Avoid.** Using `i % k` with a runtime `k` in the innermost loop and assuming
the compiler will strength-reduce it.

---

## 4. Size the thread pool to the available cores

**Practice.** Use as many threads as the process may actually run on (or
slightly fewer) and measure before tuning. Determine the allocation, not the
physical machine's CPU count.

**Evidence.** With 2 usable logical CPUs, Approach 2 peaks at **1.83× with 2
threads** and stays at 1.65–1.80× for 4–128 threads. The 128-thread
configuration is about **10% slower** than the 2-thread peak, and the 256/512
thread probe falls to **1.54×/1.49×** (19% below the peak), so the cost of
oversubscription is real but only becomes large when the worker slices get
short. Section 6.2's 4-thread point (1.94×) is within one standard deviation of
the 2-thread point, not evidence of scaling past two CPUs. The same code would
need a different thread count on a machine with a different CPU allocation.

**Avoid.** Equating "more threads" with "more performance", or copying a thread
count from a machine with a different CPU allocation.

---

## 5. Give every thread its own random generator

**Practice.** Seed one independent PRNG state per thread from a master seed
(master seed + thread id × odd constant), warm it up, and keep the state in a
local variable. Document the seeding scheme.

**Evidence.** All approaches and all thread counts produced π in the narrow range
**3.141393–3.141816**, with maximum absolute error 0.000224 (expected 1σ ≈
0.00030 at N = 30M). Approaches 2 and 3 produced **bit-identical** values for the
same thread count, and every batch frequency reproduced the T = 2 value exactly.
That demonstrates reproducibility and correct aggregation simultaneously.

**Avoid.** Calling a shared `rand()` or a global PRNG from multiple threads: it
is a data race unless locked, and locking it recreates the contention problem
solved in Practice 1.

---

## 6. Measure with a monotonic clock and a disciplined protocol

**Practice.**

- Time only the region of interest with `clock_gettime(CLOCK_MONOTONIC)`.
- Keep I/O, allocation, seed setup and result printing outside the timed region.
- For a fair parallel comparison, create all workers first and release them
  together through a start gate; record each worker's finish time and use the
  last finish as the end of the parallel region. This excludes thread
  creation/join, which has no counterpart in the single-thread baseline.
- Pin the benchmark to a fixed CPU set (`taskset`) and document it.
- Run each configuration at least 5 times; report **mean, standard deviation and
  the individual runs**.
- Keep N, seed policy, compiler flags and thread counts fixed and documented.

**Evidence.** The baseline varied by 2.9% across 5 runs (0.094655 ± 0.002753 s);
individual parallel configurations varied by 1.1–9.1%. The 1-thread Approach 2
result (0.0939 s, 1.01×) is statistically indistinguishable from the baseline,
so the gate and worker bookkeeping add no measurable cost; in contrast, timing
`pthread_create → pthread_join` would have charged every parallel configuration
for setup the baseline never pays.

**Avoid.** Single-run timings, printing inside the loop, mixing timing boundaries
between approaches, or comparing runs made with different N, pinning or
optimization flags.

---

## 7. Avoid false sharing between worker counters

**Practice.** Keep frequently updated per-thread counters in registers or on the
thread's own stack, and publish them once when the thread finishes. If counters
must live in a shared array, pad them to separate cache lines.

**Evidence / rationale.** Approach 2 keeps `count` as a stack local and writes it
to its `WorkerArg` only once after the loop. Adjacent workers therefore never
write the same cache line during sampling. This is one reason the design reaches
the 2-CPU plateau without additional contention; the lock-based design, by
contrast, concentrates every update on one shared line and loses ~23×.

**Avoid.** Placing frequently updated per-thread counters next to each other in
one unpadded array.

---

## 8. Prefer atomics over a mutex for a single counter — but prefer locality over both

**Practice.** When a shared count must be updated, an atomic add is cheaper than
a mutex because it avoids the lock/unlock pair. It does **not** remove cache-line
contention, so batching or local accumulation is still better.

**Evidence / rationale.** This lab measured mutex-based updates only. Even
uncontended, the per-hit mutex added ~0.278 s over 23.56M hits — at most about
**11.8 ns per update** (an upper bound, since the baseline also includes the
circle test) — making Approach 3 3.97× slower than the baseline with one thread.
A contended update costs far more. An atomic add would remove the lock/unlock
pair but still serializes the same cache line, so it should be treated as a
lower-overhead compromise, not a substitute for the map-reduce design.

**Avoid.** Assuming "lock-free" automatically means "scalable" for a single hot
counter.

---

## 9. Report speedup and efficiency against the real core count

**Practice.** Quote `S = T_single/T_parallel`, `E = S/T`, the allocated CPU
count, and uncertainty (standard deviation across runs). Interpret efficiency
mainly for `T ≤ cores`; beyond that it falls roughly as `1/T` by definition.

**Evidence.** Approach 2 efficiency was 100.8% at 1 thread (noise; read as
100%), 91.4% at 2, 41.4% at 4, 21.1% at 8 and 1.3% at 128. Approach 3 was 25.4%
at 1 thread because lock overhead already consumed ~75% of the baseline time.
The 1.94× point at 4 threads is within one standard deviation of the 1.89× point
at 2 threads and must not be presented as 4-core scalability.

**Avoid.** Presenting a single peak number without the core count, error bars and
the full scaling curve.

---

## 10. Verify correctness independently of parallelization and sync frequency

**Practice.** Before comparing performance, verify that every configuration
produces the same estimate under the same seed policy. Compare the shared-counter
result with the local-reduction result exactly, not just approximately, and check
the final flush of the last partial batch.

**Evidence.** Approaches 2 and 3 produced bit-identical π values per thread
count (for example 3.1413932 at T = 8), and batch frequencies *k* = 1, 10, 100
and 1,000 all produced 3.141524640 at T = 2. This proves the mutex prevented lost
updates and that batching did not drop the tail remainder. All results lie within
one standard deviation of π.

**Avoid.** Optimizing synchronization frequency without re-checking the final
flush — the easiest way to silently undercount.

---

## Quick do / don't summary

| Do | Don't |
|:--|:--|
| Private counters + single reduce | Global counter per iteration |
| Batch updates every *k* iterations | Mutex per hit |
| Countdown or block batching | `i % k` with runtime divisor in the inner loop |
| Threads ≈ usable logical CPUs | Threads ≫ cores for CPU-bound work |
| Per-thread PRNG state | Shared `rand()` |
| Start gate + monotonic clock + CPU pinning | Timing that charges parallel code for thread creation |
| 5+ runs, mean ± std | One run, or a single noisy peak |
| Report error bars and the full curve | Quote a peak as evidence of core scalability |
| Check exact counts across configurations | Trust timing without correctness checks |
