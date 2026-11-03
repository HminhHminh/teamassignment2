#include "common.h"

static long long g_batch_shared_count = 0;
static pthread_mutex_t g_batch_mutex;

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
    long long k_frequency; // Update shared variable every k points
} WorkerArgApproach3Batch;

static void* worker_approach3_batch(void* ptr) {
    WorkerArgApproach3Batch *arg = (WorkerArgApproach3Batch*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;
    long long k = arg->k_frequency;

    long long local_batch = 0;

    for (long long i = 0; i < n; i++) {
        double x = rand_coord(&seed);
        double y = rand_coord(&seed);
        if (x * x + y * y <= 1.0) {
            local_batch++;
        }

        // Synchronize every k iterations
        if ((i + 1) % k == 0) {
            if (local_batch > 0) {
                pthread_mutex_lock(&g_batch_mutex);
                g_batch_shared_count += local_batch;
                pthread_mutex_unlock(&g_batch_mutex);
                local_batch = 0;
            }
        }
    }

    // Flush any leftover counts at the end
    if (local_batch > 0) {
        pthread_mutex_lock(&g_batch_mutex);
        g_batch_shared_count += local_batch;
        pthread_mutex_unlock(&g_batch_mutex);
    }

    return NULL;
}

// Run Trade-off Experiment: Approach 3 with Synchronization Frequency k
// Returns elapsed computation time in seconds
double run_approach3_batch(long long total_points, int num_threads, long long k_frequency, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach3Batch *args = (WorkerArgApproach3Batch*)malloc(num_threads * sizeof(WorkerArgApproach3Batch));

    g_batch_shared_count = 0;
    pthread_mutex_init(&g_batch_mutex, NULL);

    long long base_chunk = total_points / num_threads;
    long long remainder = total_points % num_threads;

    for (int t = 0; t < num_threads; t++) {
        args[t].thread_id = t;
        args[t].points_to_process = base_chunk + (t == num_threads - 1 ? remainder : 0);
        args[t].seed = init_thread_seed(master_seed, t);
        args[t].k_frequency = k_frequency;
    }

    // Start timing parallel computation
    double t_start = get_time_sec();

    for (int t = 0; t < num_threads; t++) {
        pthread_create(&threads[t], NULL, worker_approach3_batch, &args[t]);
    }

    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
    }

    double t_end = get_time_sec();
    double elapsed = t_end - t_start;

    *out_circle_points = g_batch_shared_count;
    *out_pi = 4.0 * (double)g_batch_shared_count / (double)total_points;

    pthread_mutex_destroy(&g_batch_mutex);
    free(threads);
    free(args);
    return elapsed;
}
