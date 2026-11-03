# Identified Best Practices

Derived from the measured results in [`summary_tables.md`](../2_measurements/summary_tables.md)
and the analysis in [`analysis_report.md`](../4_analysis/analysis_report.md).
Each practice states the evidence, the recommended pattern, and the anti-pattern
to avoid.

---

## 1. Accumulate locally, reduce once (map-reduce)

**Practice.** Give every thread a private counter; after `pthread_join`, sum the
partial counters in the main thread.

**Evidence.** At 8 threads, local accumulation took 0.0461 s versus 0.8150 s for
a per-hit mutex — **17.7× faster** — with an identical π estimate. The reduce
phase is O(T) and negligible.

**Avoid.** Incrementing a global counter inside the sampling loop, even under a
mutex or atomic. It turns an embarrassingly parallel loop into a serial one.

---

## 2. Keep shared mutable state out of the hot loop

**Practice.** If a shared update is unavoidable, make it **rare** and batch it:
maintain a local subtotal and publish it every *k* iterations, then flush the
remainder after the loop.

**Evidence.** Changing the shared update frequency from every hit to every 1,000
iterations reduced time from 0.9705 s to 0.0271 s (**35.8×**) at T = 8, with no
change in the result (π = 3.141393 in every configuration).

**Avoid.** Locking once per element or per hit "for simplicity" — it is the most
expensive design measured in this lab.

---

## 3. Batch cheaply: count down or process blocks, do not modulo every iteration

**Practice.** Prefer a counter that triggers an update less often than the loop
body:

```c
if (++since_update == k) { publish(local); since_update = 0; }
```

or process the input in blocks of *k* and publish after each block.

**Evidence.** Even at *k* = 1,000,000 the batch variant (0.0379 s) stays about
2× above purely local accumulation (0.0195 s) because `(i + 1) % k` performs an
integer division with a runtime divisor on **every one of the 30M iterations**.
Batching removes lock traffic but can leave per-iteration arithmetic overhead.

**Avoid.** Using `i % k` with a runtime `k` in the innermost loop.

---

## 4. Size the thread pool to the available cores

**Practice.** Use as many threads as there are logical CPUs the process can
actually run on (or slightly fewer); measure before tuning.

**Evidence.** On 2 vCPUs, 2 threads gave 1.68× and 8 threads 2.08× (a plateau);
12–128 threads were **30–47% slower** than the 8-thread result. On the 12-CPU
host, 8 threads gave 4.73× — a thread count that is "oversubscribed" on one
machine is "below capacity" on another.

**Avoid.** Equating "more threads" with "more performance", or using a fixed
thread count copied from another machine.

---

## 5. Give every thread its own random generator

**Practice.** Seed one independent PRNG state per thread from a master seed
(e.g., master seed + thread id × odd constant), and keep the state in thread-local
storage. Document the seeding scheme.

**Evidence.** All approaches and all thread counts produced π in the narrow range
3.141393–3.141816, and Approaches 2 and 3 produced **identical** values for the
same configuration. This demonstrates both reproducibility and correct
aggregation.

**Avoid.** Calling a shared `rand()` / global PRNG from multiple threads: it is a
data race unless locked, and locking it recreates the contention problem solved
in Practice 1. A lock-free global counter-based generator is an alternative, but
per-thread state is simpler and faster for this workload.

---

## 6. Measure with a monotonic clock and a disciplined protocol

**Practice.**

- Time only the region of interest with `clock_gettime(CLOCK_MONOTONIC)`.
- Keep I/O, allocation, seed setup and result printing outside the timed region.
- Run each configuration at least 5 times; report **mean, standard deviation and
  the individual runs**.
- Keep N, seed policy, compiler flags and thread counts fixed and documented.
- Include thread creation/join consistently in every parallel timing so
  comparisons are like-for-like.

**Evidence.** The baseline itself varied by 6% across 5 runs; the 2-thread
Approach 2 result varied by 19%. Without repetitions and dispersion, the
1.59×/1.68× differences at high thread counts could easily be misread as real
effects.

**Avoid.** Single-run timings, printing inside the loop, or comparing runs made
with different N or optimization flags.

---

## 7. Avoid false sharing between worker counters

**Practice.** Store per-thread counters in separate cache lines when they are
written frequently — for example, in a padded struct or in thread-local stack
variables that are copied into the argument block only at the end.

**Evidence / rationale.** The implemented Approach 2 keeps `count` as a stack
local and writes it to its `WorkerArg` only once after the loop, so adjacent
workers never write the same cache line during sampling. This removes a class of
hidden contention that would otherwise show up as non-linear scaling.

**Avoid.** Placing frequently updated per-thread counters next to each other in
one array without padding.

---

## 8. Prefer atomics over a mutex for a single counter — but prefer locality over both

**Practice.** When a shared count must be updated, an atomic add is cheaper than
a mutex because it avoids the lock/unlock pair. It does **not** remove cache-line
contention, so batching or local accumulation is still better.

**Evidence / rationale.** This lab measured mutex-based updates only. The
per-hit mutex cost ~9 ns per acquisition uncontended and tens of nanoseconds
contended; an atomic still serializes the same cache line, so the scaling
problem remains. Treat atomics as a lower-overhead compromise, not a substitute
for the map-reduce design.

**Avoid.** Assuming "lock-free" automatically means "scalable" for a single hot
counter.

---

## 9. Report speedup and efficiency against the real core count

**Practice.** Quote `S = T_single/T_parallel`, `E = S/T`, the allocated CPU
count, and uncertainty. Interpret efficiency only for `T ≤ cores`; beyond that,
it falls roughly as `1/T` by definition.

**Evidence.** Approach 2 efficiency fell from 83.9% at 2 threads to 26.0% at 8
and 1.1% at 128 on a 2-vCPU VM. The nominal 2.08× peak at 8 threads is only 4%
above the 2× ceiling and sits inside run-to-run variation; treating it as
evidence of 8-core scaling would be misleading.

**Avoid.** Presenting a single peak number without the core count, error bars and
the full scaling curve.

---

## 10. Verify correctness independently of parallelization and sync frequency

**Practice.** Before comparing performance, verify that every configuration
produces the same count/estimate under the same seed. Compare the shared-counter
result with the local-reduction result exactly, not just approximately.

**Evidence.** Approaches 2 and 3 produced bit-identical π values per thread
count, and batch frequencies from 1 to 1,000,000 all produced 3.141393. This
proves the mutex prevented lost updates and batching did not drop the tail
remainder.

**Avoid.** Optimizing synchronization frequency without re-checking the final
flush of the last partial batch — the easiest way to silently undercount.

---

## Quick do / don't summary

| Do | Don't |
|:--|:--|
| Private counters + single reduce | Global counter per iteration |
| Batch updates every *k* iterations | Mutex per hit |
| Countdown/block batching | `i % k` in the inner loop |
| Threads ≈ logical CPUs | Threads ≫ cores for CPU-bound work |
| Per-thread PRNG state | Shared `rand()` |
| 5+ runs, mean ± std, monotonic clock | One run, wall clock, I/O inside timing |
| Compare against real core count and error bars | Quote a noisy peak as scalability |
| Check exact counts across configurations | Trust timing without correctness checks |
