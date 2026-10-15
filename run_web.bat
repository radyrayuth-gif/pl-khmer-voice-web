@echo off
chcp 65001 >nul
title PL Khmer Voice - SRT ^& TTS Web Studio
echo =====================================================================
echo    🌟 PL Khmer Voice - SRT ^& TTS Web Studio (FastAPI + Modern Web)
echo =====================================================================
echo.

:: បិទ process ចាស់ដែលកំពុងជាប់ port 8000 (ប្រសិនបើមាន)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [*] កំពុងបើក Browser ទៅកាន់ http://localhost:8000 ...
start "" http://localhost:8000

echo [*] កំពុងដំណើរការ Web Server (ចុច Ctrl+C ដើម្បីបិទ)...
python server.py

pause
