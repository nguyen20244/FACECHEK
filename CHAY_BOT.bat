@echo off
title Facebook Housing Monitor
cd /d "%~dp0"

REM Neu dat file nay trong thu muc project (cung cap voi main_auto.py):
if exist "main_auto.py" goto RUN

REM Neu dat ngoai project, sua duong dan ben duoi cho dung:
REM cd /d "C:\Users\nguyen\Desktop\New folder (2)\New folder\New folder\Facebook_Housing_Monitor"

if not exist "main_auto.py" (
    echo [LOI] Khong thay main_auto.py
    echo Hay copy file CHAY_BOT.bat vao cung thu muc voi main_auto.py
    echo.
    pause
    exit /b 1
)

:RUN
echo ========================================
echo   Facebook Housing Monitor
echo   Thu muc: %CD%
echo ========================================
echo.

REM Dung python trong PATH
where python >nul 2>&1
if %ERRORLEVEL%==0 (
    python main_auto.py
    goto END
)

REM Thu py launcher
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py main_auto.py
    goto END
)

echo [LOI] Khong tim thay Python. Cai Python hoac them vao PATH.
pause
exit /b 1

:END
echo.
echo Bot da dung.
pause
