@echo off
rem One-click MediaTek download-mode USB driver for snwriter.exe / bootwriter.exe.
rem
rem   install_driver.bat          install (asks for administrator rights once)
rem   install_driver.bat check    report only, changes nothing
rem
rem Both packages are the WHQL-signed MediaTek ones and run on the in-box
rem usbser.sys, so there is no test-signing mode and no reboot involved. They
rem bind the three PIDs the download protocol uses:
rem   USB\VID_0E8D&PID_0003   BROM        -> COM port   (usbvcom_brom.inf)
rem   USB\VID_0E8D&PID_2000   Preloader   -> COM port   (usbvcom.inf)
rem   USB\VID_0E8D&PID_2001   DA          -> COM port   (usbvcom.inf)
rem mtkclient talks to those COM ports through pyserial; without them the tool
rem sits in "Waiting for PreLoader VCOM" forever and the board looks dead.
rem No UsbDk / WinUSB is required: this mtkclient checkout has the USE_USBDK
rem option commented out in Library/Connection/usblib.py, so it never asks.
rem
rem An install is mirrored into drivers\install.log, because the elevated copy
rem runs in its own console window and that is the only record left afterwards.
rem
rem Pure ASCII on purpose: cmd reads .bat files in the OEM codepage.
setlocal
cd /d "%~dp0"

set "LOG=%~dp0install.log"
set "CAP=%TEMP%\snwriter_driver.out"

if /i "%~1"=="check" goto :check

rem ---- one elevation, then the real work runs in the elevated copy ----------
net session >nul 2>&1
if not errorlevel 1 goto :admin
echo Requesting administrator rights ...
echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\snwriter_uac.vbs"
echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\snwriter_uac.vbs"
"%temp%\snwriter_uac.vbs"
del "%temp%\snwriter_uac.vbs" >nul 2>&1
exit /b

:admin
echo ==== install %date% %time% ==== > "%LOG%" 2>nul
echo.
echo Installing the MediaTek download-mode USB drivers ...
rem /install also binds the package to devices already in the device tree, and a
rem package that is already in the store is reported and skipped - so running
rem this twice is safe.
for %%F in (usbvcom_brom.inf usbvcom.inf) do (
  echo.
  echo ---- %%F
  pnputil /add-driver "%~dp0infs\%%F" /install > "%CAP%" 2>&1
  type "%CAP%"
  type "%CAP%" >> "%LOG%" 2>nul
)
echo.
echo Re-enumerating the device tree ...
pnputil /scan-devices >nul 2>&1

:check
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_driver.ps1" > "%CAP%" 2>&1
type "%CAP%"
if exist "%LOG%" type "%CAP%" >> "%LOG%" 2>nul
del "%CAP%" >nul 2>&1
echo.
if /i not "%~1"=="check" (
  echo If the machine is plugged in right now: unplug the cable, power the device
  echo off and plug in again, so Windows re-binds the freshly installed driver.
  echo Log file: drivers\install.log
  echo.
  pause
)
exit /b
