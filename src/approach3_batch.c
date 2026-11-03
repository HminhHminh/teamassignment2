#include "common.h"

static long long g_batch_shared_count = 0;
static pthread_mutex_t g_batch_mutex;

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
    long long k_frequency; // Update shared variable every k points
    StartGate *start_gate;
    double finished_at;
} WorkerArgApproach3Batch;

static void* worker_approach3_batch(void* ptr) {
    WorkerArgApproach3Batch *arg = (WorkerArgApproach3Batch*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;
    long long k = arg->k_frequency;

    long long local_batch = 0;

    if (!start_gate_wait(arg->start_gate)) return NULL;

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

    arg->finished_at = get_time_sec();
    return NULL;
}

// Run Trade-off Experiment: Approach 3 with Synchronization Frequency k
// Returns elapsed computation time in seconds
double run_approach3_batch(long long total_points, int num_threads, long long k_frequency, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach3Batch *args = (WorkerArgApproach3Batch*)malloc(num_threads * sizeof(WorkerArgApproach3Batch));
    StartGate start_gate;
    if (threads == NULL || args == NULL || k_frequency < 1 || start_gate_init(&start_gate) != 0) {
        fprintf(stderr, "Approach 3 batch: invalid setup or allocation failure\n");
        free(threads);
        free(args);
        *out_circle_points = 0;
        *out_pi = 0.0;
        return 0.0;
    }

    g_batch_shared_count = 0;
    int mutex_error = pthread_mutex_init(&g_batch_mutex, NULL);
    if (mutex_error != 0) {
        fprintf(stderr, "Approach 3 batch: pthread_mutex_init failed (%d)\n", mutex_error);
        start_gate_destroy(&start_gate);
        free(threads);
        free(args);
        *out_circle_points = 0;
        *out_pi = 0.0;
        return 0.0;
    }

    long long base_chunk = total_points / num_threads;
    long long remainder = total_points % num_threads;

    for (int t = 0; t < num_threads; t++) {
        args[t].thread_id = t;
        args[t].points_to_process = base_chunk + (t == num_threads - 1 ? remainder : 0);
        args[t].seed = init_thread_seed(master_seed, t);
        args[t].k_frequency = k_frequency;
        args[t].start_gate = &start_gate;
    }

    // Create every worker before starting the timed computation.
    int created = 0;
    for (int t = 0; t < num_threads; t++) {
        int error = pthread_create(&threads[t], NULL, worker_approach3_batch, &args[t]);
        if (error != 0) {
            fprintf(stderr, "Approach 3 batch: pthread_create failed (%d)\n", error);
            start_gate_cancel(&start_gate);
            for (int j = 0; j < created; j++) pthread_join(threads[j], NULL);
            pthread_mutex_destroy(&g_batch_mutex);
            start_gate_destroy(&start_gate);
            free(threads);
            free(args);
            *out_circle_points = 0;
            *out_pi = 0.0;
            return 0.0;
        }
        created++;
    }

    double t_start;
    start_gate_release(&start_gate, &t_start);

    double last_worker_finished = t_start;
    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
        if (args[t].finished_at > last_worker_finished)
            last_worker_finished = args[t].finished_at;
    }

    double elapsed = last_worker_finished - t_start;

    *out_circle_points = g_batch_shared_count;
    *out_pi = 4.0 * (double)g_batch_shared_count / (double)total_points;

    pthread_mutex_destroy(&g_batch_mutex);
    start_gate_destroy(&start_gate);
    free(threads);
    free(args);
    return elapsed;
}
