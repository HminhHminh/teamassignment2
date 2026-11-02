#include "common.h"

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
    long long local_circle_count;
} WorkerArgApproach2;

static void* worker_approach2(void* ptr) {
    WorkerArgApproach2 *arg = (WorkerArgApproach2*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;
    long long count = 0; // Local counter on thread stack (avoids false sharing)

    for (long long i = 0; i < n; i++) {
        double x = rand_coord(&seed);
        double y = rand_coord(&seed);
        if (x * x + y * y <= 1.0) {
            count++;
        }
    }

    arg->local_circle_count = count;
    return NULL;
}

// Run Multi-threaded Monte Carlo simulation with Local Accumulation (Map-Reduce pattern)
// Returns elapsed computation time in seconds
double run_approach2(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach2 *args = (WorkerArgApproach2*)malloc(num_threads * sizeof(WorkerArgApproach2));

    long long base_chunk = total_points / num_threads;
    long long remainder = total_points % num_threads;

    for (int t = 0; t < num_threads; t++) {
        args[t].thread_id = t;
        args[t].points_to_process = base_chunk + (t == num_threads - 1 ? remainder : 0);
        args[t].seed = init_thread_seed(master_seed, t);
        args[t].local_circle_count = 0;
    }

    // Start timing parallel computation phase
    double t_start = get_time_sec();

    // Map phase: dispatch threads to compute partial results independently
    for (int t = 0; t < num_threads; t++) {
        pthread_create(&threads[t], NULL, worker_approach2, &args[t]);
    }

    // Reduce phase: wait for threads to complete and aggregate partial results
    long long total_circle_count = 0;
    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
        total_circle_count += args[t].local_circle_count;
    }

    double t_end = get_time_sec();
    double elapsed = t_end - t_start;

    *out_circle_points = total_circle_count;
    *out_pi = 4.0 * (double)total_circle_count / (double)total_points;

    free(threads);
    free(args);
    return elapsed;
}
