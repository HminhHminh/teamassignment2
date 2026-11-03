#include "common.h"

typedef struct {
    int thread_id;
    long long points_to_process;
    uint64_t seed;
    long long local_circle_count;
    StartGate *start_gate;
    double finished_at;
} WorkerArgApproach2;

static void* worker_approach2(void* ptr) {
    WorkerArgApproach2 *arg = (WorkerArgApproach2*)ptr;
    uint64_t seed = arg->seed;
    long long n = arg->points_to_process;
    long long count = 0; // Local counter on thread stack (avoids false sharing)

    if (!start_gate_wait(arg->start_gate)) return NULL;

    for (long long i = 0; i < n; i++) {
        double x = rand_coord(&seed);
        double y = rand_coord(&seed);
        if (x * x + y * y <= 1.0) {
            count++;
        }
    }

    arg->local_circle_count = count;
    arg->finished_at = get_time_sec();
    return NULL;
}

// Run Multi-threaded Monte Carlo simulation with Local Accumulation (Map-Reduce pattern)
// Returns elapsed computation time in seconds
double run_approach2(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    pthread_t *threads = (pthread_t*)malloc(num_threads * sizeof(pthread_t));
    WorkerArgApproach2 *args = (WorkerArgApproach2*)malloc(num_threads * sizeof(WorkerArgApproach2));
    StartGate start_gate;
    if (threads == NULL || args == NULL || start_gate_init(&start_gate) != 0) {
        fprintf(stderr, "Approach 2: could not allocate or initialize worker setup\n");
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
        args[t].local_circle_count = 0;
        args[t].start_gate = &start_gate;
    }

    // Create every worker before starting the timed computation.
    int created = 0;
    for (int t = 0; t < num_threads; t++) {
        int error = pthread_create(&threads[t], NULL, worker_approach2, &args[t]);
        if (error != 0) {
            fprintf(stderr, "Approach 2: pthread_create failed (%d)\n", error);
            start_gate_cancel(&start_gate);
            for (int j = 0; j < created; j++) pthread_join(threads[j], NULL);
            start_gate_destroy(&start_gate);
            free(threads);
            free(args);
            *out_circle_points = 0;
            *out_pi = 0.0;
            return 0.0;
        }
        created++;
    }

    // Release the waiting workers and start timing only the parallel work.
    double t_start;
    start_gate_release(&start_gate, &t_start);

    // Join and reduce after work. The join/reduction time is excluded below.
    long long total_circle_count = 0;
    double last_worker_finished = t_start;
    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
        total_circle_count += args[t].local_circle_count;
        if (args[t].finished_at > last_worker_finished)
            last_worker_finished = args[t].finished_at;
    }

    double elapsed = last_worker_finished - t_start;

    *out_circle_points = total_circle_count;
    *out_pi = 4.0 * (double)total_circle_count / (double)total_points;

    start_gate_destroy(&start_gate);
    free(threads);
    free(args);
    return elapsed;
}
