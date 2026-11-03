#!/usr/bin/env bash
# Rebuild, re-measure, replot and verify the whole submission package.
#
# Usage:
#   bash reproduce.sh            # default: 2 CPUs, 5 runs, 30M points
#   CPUS=4 bash reproduce.sh     # pin to a different CPU count
#   SKIP_PLOTS=1 bash reproduce.sh
#
# Requirements: gcc with pthreads; python3; numpy + matplotlib
# (pip install -r requirements.txt). On Linux, taskset pins the benchmark.

set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
CPUS="${CPUS:-2}"
EXE="1_source_code/monte_carlo"

echo "== Checking tools =="
command -v "${PYTHON}" >/dev/null 2>&1 || {
    echo "error: ${PYTHON} not found" >&2
    exit 1
}
command -v gcc >/dev/null 2>&1 || {
    echo "error: gcc not found" >&2
    exit 1
}
if [ "${SKIP_PLOTS:-0}" != "1" ]; then
    "${PYTHON}" -c "import numpy, matplotlib" >/dev/null 2>&1 || {
        echo "error: numpy/matplotlib missing. Run: ${PYTHON} -m pip install -r requirements.txt" >&2
        exit 1
    }
fi

echo "== Building =="
make -C 1_source_code

echo "== Running the benchmark (CPUS=${CPUS}) =="
"${PYTHON}" 1_source_code/run_benchmarks.py --exe "${EXE}" --cpus "${CPUS}"

if [ "${SKIP_PLOTS:-0}" != "1" ]; then
    echo "== Plotting and writing summary tables =="
    "${PYTHON}" 1_source_code/plot_results.py
fi

echo "== Verifying =="
"${PYTHON}" verify.py

echo "Done."
