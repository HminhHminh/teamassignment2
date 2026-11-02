#include "common.h"

static long long g_shared_circle_count = 0;
static pthread_mutex_t g_mutex;

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
} WorkerArgApproach3;

static void* worker_approach3(void* ptr) {
    WorkerArgApproach3 *arg = (WorkerArgApproach3*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;

    for (long long i = 0; i < n; i++) {
        double x = rand_coord(&seed);
        double y = rand_coord(&seed);
        if (x * x + y * y <= 1.0) {
            // Critical section: acquire mutex on every single hit
            pthread_mutex_lock(&g_mutex);
            g_shared_circle_count++;
            pthread_mutex_unlock(&g_mutex);
        }
    }

    return NULL;
}

// Run Multi-threaded Monte Carlo simulation with Shared Variable & Mutex
// Returns elapsed computation time in seconds
double run_approach3(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach3 *args = (WorkerArgApproach3*)malloc(num_threads * sizeof(WorkerArgApproach3));

    g_shared_circle_count = 0;
    pthread_mutex_init(&g_mutex, NULL);

    long long base_chunk = total_points / num_threads;
    long long remainder = total_points % num_threads;

    for (int t = 0; t < num_threads; t++) {
        args[t].thread_id = t;
        args[t].points_to_process = base_chunk + (t == num_threads - 1 ? remainder : 0);
        args[t].seed = init_thread_seed(master_seed, t);
    }

    // Start timing parallel computation
    double t_start = get_time_sec();

    for (int t = 0; t < num_threads; t++) {
        pthread_create(&threads[t], NULL, worker_approach3, &args[t]);
    }

    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
    }

    double t_end = get_time_sec();
    double elapsed = t_end - t_start;

    *out_circle_points = g_shared_circle_count;
    *out_pi = 4.0 * (double)g_shared_circle_count / (double)total_points;

    pthread_mutex_destroy(&g_mutex);
    free(threads);
    free(args);
    return elapsed;
}
