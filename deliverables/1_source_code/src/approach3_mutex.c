#include "common.h"

static long long g_shared_circle_count = 0;
static pthread_mutex_t g_mutex;

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
    StartGate *start_gate;
    double finished_at;
} WorkerArgApproach3;

static void* worker_approach3(void* ptr) {
    WorkerArgApproach3 *arg = (WorkerArgApproach3*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;

    if (!start_gate_wait(arg->start_gate)) return NULL;

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

    arg->finished_at = get_time_sec();
    return NULL;
}

// Run Multi-threaded Monte Carlo simulation with Shared Variable & Mutex
// Returns elapsed computation time in seconds
double run_approach3(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach3 *args = (WorkerArgApproach3*)malloc(num_threads * sizeof(WorkerArgApproach3));
    StartGate start_gate;
    if (threads == NULL || args == NULL || start_gate_init(&start_gate) != 0) {
        fprintf(stderr, "Approach 3: could not allocate or initialize worker setup\n");
        free(threads);
        free(args);
        *out_circle_points = 0;
        *out_pi = 0.0;
        return 0.0;
    }

    g_shared_circle_count = 0;
    int mutex_error = pthread_mutex_init(&g_mutex, NULL);
    if (mutex_error != 0) {
        fprintf(stderr, "Approach 3: pthread_mutex_init failed (%d)\n", mutex_error);
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
        args[t].start_gate = &start_gate;
    }

    // Create every worker before starting the timed computation.
    int created = 0;
    for (int t = 0; t < num_threads; t++) {
        int error = pthread_create(&threads[t], NULL, worker_approach3, &args[t]);
        if (error != 0) {
            fprintf(stderr, "Approach 3: pthread_create failed (%d)\n", error);
            start_gate_cancel(&start_gate);
            for (int j = 0; j < created; j++) pthread_join(threads[j], NULL);
            pthread_mutex_destroy(&g_mutex);
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

    *out_circle_points = g_shared_circle_count;
    *out_pi = 4.0 * (double)g_shared_circle_count / (double)total_points;

    pthread_mutex_destroy(&g_mutex);
    start_gate_destroy(&start_gate);
    free(threads);
    free(args);
    return elapsed;
}
