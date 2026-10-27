@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0python\python.exe"
if not exist "%PY%" goto nopy
"%PY%" "%~dp0main.py" barcode %*
echo.
pause
exit /b 0
:nopy
echo [ERROR] python.exe not found: %PY%
echo Please unzip the whole folder.
echo.
pause
exit /b 1
