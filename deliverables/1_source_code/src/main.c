#include "common.h"
#include <string.h>
#include <math.h>

// Forward declarations
double run_approach1(long long total_points, uint64_t master_seed, long long *out_circle_points, double *out_pi);
double run_approach2(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi);
double run_approach3(long long total_points, int num_threads, uint64_t master_seed, long long *out_circle_points, double *out_pi);
double run_approach3_batch(long long total_points, int num_threads, long long k_frequency, uint64_t master_seed, long long *out_circle_points, double *out_pi);

static void print_usage(const char* prog) {
    printf("Usage: %s [options]\n", prog);
    printf("Options:\n");
    printf("  -a, --approach <1|2|3|batch>   Approach to run (default: 2)\n");
    printf("  -n, --points <N>               Total random points (default: 10000000)\n");
    printf("  -t, --threads <T>              Number of threads (default: 4)\n");
    printf("  -k, --frequency <K>            Sync frequency for batch approach (default: 1000)\n");
    printf("  -s, --seed <S>                 Master random seed (default: 123456789)\n");
    printf("  -r, --runs <R>                 Number of repetitions (default: 1)\n");
    printf("  --csv                          Output single-line CSV format: approach,threads,points,k,run,time,pi\n");
    printf("  -h, --help                     Display this help message\n");
}

int main(int argc, char* argv[]) {
    char approach[32] = "2";
    long long total_points = 10000000LL; // 10^7 default
    int num_threads = 4;
    long long k_frequency = 1000LL;
    uint64_t master_seed = 123456789ULL;
    int runs = 1;
    bool csv_mode = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-a") == 0 || strcmp(argv[i], "--approach") == 0) {
            if (++i < argc) strncpy(approach, argv[i], sizeof(approach) - 1);
        } else if (strcmp(argv[i], "-n") == 0 || strcmp(argv[i], "--points") == 0) {
            if (++i < argc) total_points = atoll(argv[i]);
        } else if (strcmp(argv[i], "-t") == 0 || strcmp(argv[i], "--threads") == 0) {
            if (++i < argc) num_threads = atoi(argv[i]);
        } else if (strcmp(argv[i], "-k") == 0 || strcmp(argv[i], "--frequency") == 0) {
            if (++i < argc) k_frequency = atoll(argv[i]);
        } else if (strcmp(argv[i], "-s") == 0 || strcmp(argv[i], "--seed") == 0) {
            if (++i < argc) master_seed = (uint64_t)strtoull(argv[i], NULL, 10);
        } else if (strcmp(argv[i], "-r") == 0 || strcmp(argv[i], "--runs") == 0) {
            if (++i < argc) runs = atoi(argv[i]);
        } else if (strcmp(argv[i], "--csv") == 0) {
            csv_mode = true;
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_usage(argv[0]);
            return 1;
        }
    }

    if (num_threads < 1) num_threads = 1;
    if (total_points < 1) total_points = 1000;
    if (runs < 1) runs = 1;

    double *times = (double*)malloc(runs * sizeof(double));
    double *pis = (double*)malloc(runs * sizeof(double));
    long long *circle_counts = (long long*)malloc(runs * sizeof(long long));

    for (int r = 0; r < runs; r++) {
        // Vary run seed deterministically if needed, or maintain master_seed for exact reproducibility
        uint64_t current_seed = master_seed + (uint64_t)r * 99991ULL;
        long long in_circle = 0;
        double pi_val = 0.0;
        double elapsed = 0.0;

        if (strcmp(approach, "1") == 0) {
            elapsed = run_approach1(total_points, current_seed, &in_circle, &pi_val);
        } else if (strcmp(approach, "2") == 0) {
            elapsed = run_approach2(total_points, num_threads, current_seed, &in_circle, &pi_val);
        } else if (strcmp(approach, "3") == 0) {
            elapsed = run_approach3(total_points, num_threads, current_seed, &in_circle, &pi_val);
        } else if (strcmp(approach, "batch") == 0) {
            elapsed = run_approach3_batch(total_points, num_threads, k_frequency, current_seed, &in_circle, &pi_val);
        } else {
            fprintf(stderr, "Error: Unknown approach '%s'\n", approach);
            free(times); free(pis); free(circle_counts);
            return 1;
        }

        times[r] = elapsed;
        pis[r] = pi_val;
        circle_counts[r] = in_circle;

        if (csv_mode) {
            printf("%s,%d,%lld,%lld,%d,%.6f,%.9f\n",
                   approach, (strcmp(approach, "1") == 0 ? 1 : num_threads),
                   total_points, k_frequency, r + 1, elapsed, pi_val);
        }
    }

    if (!csv_mode) {
        double sum_time = 0.0;
        double sum_pi = 0.0;
        for (int r = 0; r < runs; r++) {
            sum_time += times[r];
            sum_pi += pis[r];
        }
        double avg_time = sum_time / runs;
        double avg_pi = sum_pi / runs;
        double std_time = 0.0;
        for (int r = 0; r < runs; r++) {
            std_time += (times[r] - avg_time) * (times[r] - avg_time);
        }
        std_time = sqrt(std_time / runs);

        const double TRUE_PI = 3.14159265358979323846;
        double abs_error = fabs(avg_pi - TRUE_PI);
        double throughput = ((double)total_points / avg_time) / 1e6;

        printf("\n=======================================================\n");
        printf(" MONTE CARLO PI ESTIMATION SUMMARY\n");
        printf("=======================================================\n");
        printf(" Approach:          %s\n", approach);
        printf(" Total Points:      %lld\n", total_points);
        printf(" Threads:           %d\n", (strcmp(approach, "1") == 0 ? 1 : num_threads));
        if (strcmp(approach, "batch") == 0) {
            printf(" Sync Frequency(k): %lld\n", k_frequency);
        }
        printf(" Repetitions:       %d\n", runs);
        printf(" Points in Circle:  %lld\n", circle_counts[0]);
        printf(" Estimated Pi:      %.9f\n", avg_pi);
        printf(" True Pi:           %.15f\n", TRUE_PI);
        printf(" Absolute Error:    %.9f\n", abs_error);
        printf(" Average Time:      %.6f s\n", avg_time);
        if (runs > 1) {
            printf(" Std Dev Time:      %.6f s\n", std_time);
        }
        printf(" Throughput:        %.2f Mpoints/s\n", throughput);
        printf("=======================================================\n\n");
    }

    free(times);
    free(pis);
    free(circle_counts);
    return 0;
}
