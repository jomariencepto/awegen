@echo off
REM ============================================================================
REM Quick Start: Run Exam System as Network Server
REM This script automatically finds your IP and starts the server
REM ============================================================================

echo.
echo ============================================================================
echo  EXAM GENERATION SYSTEM - NETWORK SERVER LAUNCHER
echo ============================================================================
echo.

REM Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| find "IPv4 Address"') do set IP=%%a

REM Trim whitespace
for /f "tokens=* delims= " %%a in ("%IP%") do set IP=%%a

echo Your Laptop IP: %IP%
echo.
echo Starting server in backend folder...
echo.

REM Navigate to backend
cd backend

REM Run the server
python run_server.py

REM If python fails, try python3
if errorlevel 1 (
    echo.
    echo Trying with python3...
    python3 run_server.py
)

pause
