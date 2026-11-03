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

/* Threads wait here until setup is complete and the measured work can start. */
typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    int start;
    int cancel;
} StartGate;

static inline int start_gate_init(StartGate *gate) {
    gate->start = 0;
    gate->cancel = 0;
    int error = pthread_mutex_init(&gate->mutex, NULL);
    if (error != 0) return error;
    error = pthread_cond_init(&gate->condition, NULL);
    if (error != 0) pthread_mutex_destroy(&gate->mutex);
    return error;
}

static inline int start_gate_wait(StartGate *gate) {
    pthread_mutex_lock(&gate->mutex);
    while (!gate->start && !gate->cancel)
        pthread_cond_wait(&gate->condition, &gate->mutex);
    int should_start = gate->start;
    pthread_mutex_unlock(&gate->mutex);
    return should_start;
}

static inline void start_gate_release(StartGate *gate, double *start_time) {
    pthread_mutex_lock(&gate->mutex);
    *start_time = get_time_sec();
    gate->start = 1;
    pthread_cond_broadcast(&gate->condition);
    pthread_mutex_unlock(&gate->mutex);
}

static inline void start_gate_cancel(StartGate *gate) {
    pthread_mutex_lock(&gate->mutex);
    gate->cancel = 1;
    pthread_cond_broadcast(&gate->condition);
    pthread_mutex_unlock(&gate->mutex);
}

static inline void start_gate_destroy(StartGate *gate) {
    pthread_cond_destroy(&gate->condition);
    pthread_mutex_destroy(&gate->mutex);
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
