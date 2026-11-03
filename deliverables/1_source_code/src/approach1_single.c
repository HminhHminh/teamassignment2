#include "common.h"

// Run single-threaded Monte Carlo simulation
// Returns elapsed computation time in seconds
double run_approach1(long long total_points, uint64_t master_seed, long long *out_circle_points, double *out_pi) {
    uint64_t seed = init_thread_seed(master_seed, 0);
    long long circle_count = 0;

    // Start timing strictly for the computation phase
    double t_start = get_time_sec();

    for (long long i = 0; i < total_points; i++) {
        double x = rand_coord(&seed);
        double y = rand_coord(&seed);
        if (x * x + y * y <= 1.0) {
            circle_count++;
        }
    }

    double t_end = get_time_sec();
    double elapsed = t_end - t_start;

    *out_circle_points = circle_count;
    *out_pi = 4.0 * (double)circle_count / (double)total_points;
    return elapsed;
}
