@echo off
REM Rebuild, re-measure, replot and verify the package on Windows.
REM Absolute timings will differ from the submitted 2-CPU Linux environment.
setlocal
cd /d "%~dp0"

where gcc >nul 2>nul
if errorlevel 1 (
    echo error: gcc not found in PATH
    exit /b 1
)

python -c "import numpy, matplotlib" >nul 2>nul
if errorlevel 1 (
    echo error: numpy/matplotlib missing. Run: python -m pip install -r requirements.txt
    exit /b 1
)

echo == Building ==
call 1_source_code\build.bat
if not exist 1_source_code\monte_carlo.exe (
    echo error: build failed
    exit /b 1
)

echo == Running the benchmark ==
python 1_source_code\run_benchmarks.py --exe 1_source_code\monte_carlo.exe --no-affinity
if errorlevel 1 exit /b 1

echo == Plotting and writing summary tables ==
python 1_source_code\plot_results.py
if errorlevel 1 exit /b 1

echo == Verifying ==
python verify.py
if errorlevel 1 exit /b 1

echo Done.
