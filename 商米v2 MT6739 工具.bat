@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0python\python.exe"
if not exist "%PY%" goto nopy
"%PY%" "%~dp0main.py" %*
echo.
pause
exit /b 0
:nopy
echo [ERROR] python.exe not found:
echo   %PY%
echo Please unzip the whole folder instead of copying part of it.
echo.
pause
exit /b 1
