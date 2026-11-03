#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <pthread.h>

// High-resolution timer utility using standard POSIX clock_gettime
// Monotonic clock provides nanosecond precision without pulling in heavy Windows headers
static inline double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

// Fast thread-safe PRNG: Xorshift64*
// Each thread holds its own state pointer, ensuring zero shared state and zero locks.
static inline uint64_t xorshift64star(uint64_t *state) {
    uint64_t x = *state;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    *state = x;
    return x * 0x2545F4914F6CDD1DULL;
}

// Generate uniform double in [-1.0, 1.0]
static inline double rand_coord(uint64_t *state) {
    // 53 bits of precision for double
    uint64_t r = xorshift64star(state);
    return ((double)(r >> 11) / (double)(1ULL << 53)) * 2.0 - 1.0;
}

// Seed initializer: splits a master seed into distinct independent seeds per thread
static inline uint64_t init_thread_seed(uint64_t master_seed, int thread_id) {
    uint64_t s = master_seed + ((uint64_t)thread_id + 1) * 0x9E3779B97F4A7C15ULL;
    // Warm up PRNG state
    for (int i = 0; i < 16; i++) {
        xorshift64star(&s);
    }
    return s == 0 ? 1 : s;
}

#endif // COMMON_H
