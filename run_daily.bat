@echo off
chcp 65001 >nul
echo ====================================================
echo   Paper Push starting...
echo   Current time: %date% %time%
echo   Default command: daily
echo ====================================================
echo.

cd /d "%~dp0"
set PYTHONUTF8=1
py -3 -u main.py daily %*

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] main.py daily finished successfully.
) else (
    echo.
    echo [ERROR] main.py daily failed. Check the terminal output.
)

echo.
echo Window will close in 15 seconds...
timeout /t 15 >nul
