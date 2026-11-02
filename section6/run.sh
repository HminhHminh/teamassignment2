#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

POINTS="${1:-30000000}"
REPEATS="${2:-5}"
SEED="${3:-123456789}"
CORES="$(getconf _NPROCESSORS_ONLN)"
RESULTS="results/section6_results.csv"

if ! [[ "$POINTS" =~ ^[1-9][0-9]*$ && "$REPEATS" =~ ^[1-9][0-9]*$ && "$SEED" =~ ^[0-9]+$ ]]; then
    echo "Usage: bash section6/run.sh [points] [repetitions] [seed]" >&2
    exit 1
fi

make
mkdir -p results
printf 'approach,threads,points,k,run,time,pi\n' > "$RESULTS"

run_case() {
    local approach="$1" threads="$2" frequency="$3"
    ./monte_carlo -a "$approach" -t "$threads" -n "$POINTS" \
        -k "$frequency" -s "$SEED" -r "$REPEATS" --csv >> "$RESULTS"
}

# 6.2: below, near, and above the machine's logical CPU count.
# 6.3: local accumulation and shared mutex with identical configurations.
THREAD_COUNTS="$(printf '%s\n' 1 2 4 8 16 "$CORES" "$((CORES + 1))" "$((CORES * 2))" 100 | sort -nu)"
for threads in $THREAD_COUNTS; do
    if (( threads <= POINTS )); then
        run_case 2 "$threads" 1
        run_case 3 "$threads" 1
    fi
done

# 6.1: Approach 3's batch variant, at a fixed thread count.
if (( CORES <= POINTS )); then
    for frequency in 1 10 100 1000; do
        run_case batch "$CORES" "$frequency"
    done
fi

python3 section6/report.py "$RESULTS" "$CORES"
echo "Section 6 outputs are in results/section6_*."
