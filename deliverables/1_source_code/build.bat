@echo off
echo Building Monte Carlo Pi Estimation...
gcc -O3 -pthread -Wall -Wextra -Isrc src/main.c src/approach1_single.c src/approach2_local.c src/approach3_mutex.c src/approach3_batch.c -o monte_carlo.exe -lm
if %ERRORLEVEL% EQU 0 (
    echo Compilation successful: monte_carlo.exe
) else (
    echo Compilation failed!
)
