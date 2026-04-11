@echo off
:: ============================================================
:: auto_dairy – Double-click runner (Windows)
:: ============================================================
:: Runs diary_generator.py once with the current Python
:: interpreter. A console window stays open after the script
:: finishes so you can review any log output or error messages.
:: ============================================================

cd /d "%~dp0"

:: Check that Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on PATH.
    echo Please install Python 3.10+ and add it to your PATH.
    pause
    exit /b 1
)

:: Check that .env exists (created from .env.example)
if not exist ".env" (
    echo [ERROR] .env file not found.
    echo Please copy .env.example to .env and fill in your settings.
    pause
    exit /b 1
)

echo Running auto_dairy...
python diary_generator.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] diary_generator.py exited with an error (see above).
)

echo.
echo Done. Press any key to close this window.
pause >nul
