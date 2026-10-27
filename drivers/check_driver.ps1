# Reports whether the MediaTek download-mode USB drivers are in place.
# Read-only: it never installs or removes anything, so it is safe to run any time.
#
#   powershell -ExecutionPolicy Bypass -File check_driver.ps1
#   drivers\install_driver.bat check      calls this after installing
#
# The two checks are deliberately locale independent: the driver store is probed
# by folder name and the device bindings by property key, because pnputil and
# Device Manager print localised labels that a script cannot grep for.
$ErrorActionPreference = 'Continue'

# PID -> what the board is doing in that mode and which service must own it.
# The verdict keys off DEVPKEY_Device_Service, not the inf name: the property
# returns the *published* name (oem37.inf), which says nothing about which
# package it came from, while the service is exactly the discriminator.
$Expected = [ordered]@{
  '0003' = 'BROM'
  '2000' = 'Preloader'
  '2001' = 'DA'
}

$Repo = Join-Path $env:SystemRoot 'System32\DriverStore\FileRepository'
$Stored = @()
foreach ($pkg in @('usbvcom_brom', 'usbvcom')) {
  $hit = Get-ChildItem -Path $Repo -Directory -Filter ($pkg + '.inf_*') -ErrorAction SilentlyContinue
  if ($hit) { $Stored += $pkg }
}

Write-Host '== driver packages in the Windows driver store =='
foreach ($pkg in @('usbvcom_brom', 'usbvcom')) {
  if ($Stored -contains $pkg) { Write-Host ('   [ok]    ' + $pkg + '.inf') }
  else { Write-Host ('   [MISSING] ' + $pkg + '.inf') }
}
if ($Stored.Count -lt 2) {
  Write-Host '   run drivers\install_driver.bat once, then check again'
}

Write-Host ''
Write-Host '== MediaTek devices Windows has seen (VID_0E8D) =='
$devices = Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB\*VID_0E8D*' }
$seen = @{}
foreach ($d in $devices) {
  # InstanceId is USB\VID_0E8D&PID_xxxx\<serial>; the second component says which
  # mode the board enumerated in.
  $parts = $d.InstanceId -split '\\'
  if ($parts.Count -lt 2) { continue }
  if ($parts[1] -notmatch 'PID_([0-9A-Fa-f]{4})') { continue }
  $pid4 = $Matches[1].ToUpper()

  $inf = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue).Data
  $svc = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_Service' -ErrorAction SilentlyContinue).Data
  $cls = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_Class' -ErrorAction SilentlyContinue).Data

  # Dedup on PID *and* binding, not PID alone: PID_2000 legitimately shows up twice
  # on a machine that has both the COM-port package and SP Flash Tool's WinUSB.
  $key = $pid4 + '|' + $svc + '|' + $inf
  if ($seen.ContainsKey($key)) { continue }
  $seen[$key] = $true

  $line = '   PID_' + $pid4
  if ($Expected.Contains($pid4)) { $line += '  (' + $Expected[$pid4] + ')' }
  $line += '  inf=' + $(if ($inf) { $inf } else { '-' })
  $line += '  class=' + $(if ($cls) { $cls } else { '-' })
  $line += '  driver=' + $(if ($svc) { $svc } else { 'NONE' })

  if (-not $Expected.Contains($pid4)) {
    $line += '   (not a download-mode PID, informational)'
    Write-Host $line
    continue
  }
  if ($svc -eq 'usbser') {
    # usbser.sys = the MTK package bound it as a COM port, which is what
    # mtkclient and the vendor SN Writer both want.
    $line += '   [ok]'
  }
  elseif ($svc -eq 'WinUSB') {
    # SP Flash Tool / Zadig bind WinUSB to PID_2000. mtkclient can use it through
    # libusb, the vendor SN Writer cannot, and the two fight over one instance.
    $line += '   [WinUSB] mtkclient works; a vendor COM-port tool would not'
  }
  elseif (-not $svc) {
    $line += '   [NO DRIVER] the board enumerates but nothing can talk to it'
  }
  else {
    $line += '   [unexpected driver service ' + $svc + ', expected usbser]'
  }
  Write-Host $line
}
if ($seen.Count -eq 0) {
  Write-Host '   none yet - plug the machine in once (powered off, no keys held) so Windows records it'
}

Write-Host ''
$missing = @()
foreach ($pkg in @('usbvcom_brom', 'usbvcom')) { if ($Stored -notcontains $pkg) { $missing += $pkg } }
if ($missing.Count -eq 0) {
  Write-Host 'RESULT: driver packages installed.'
  exit 0
}
Write-Host ('RESULT: missing ' + ($missing -join ', ') + ' - run drivers\install_driver.bat')
exit 1
