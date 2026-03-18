@echo off
chcp 65001 >nul
echo ====================================================
echo   论文推送系统启动中...
echo   当前时间: %date% %time%
echo ====================================================
echo.

cd /d "%~dp0"
set PYTHONUTF8=1
py -3 main.py

if %ERRORLEVEL% equ 0 (
    echo.
    echo [成功] 论文抓取分析已完成，已推送到飞书。
) else (
    echo.
    echo [错误] 运行出错，请检查日志输出。
)

echo.
echo 窗口将在 15 秒后自动关闭...
timeout /t 15 >nul
