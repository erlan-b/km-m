param(
  [ValidateSet('auto', 'emulator', 'usb')]
  [string]$Mode = 'auto',
  [int]$Port = 8000,
  [switch]$SkipPubGet,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Clear-ProxyEnv {
  $proxyVars = @(
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'ALL_PROXY',
    'http_proxy',
    'https_proxy',
    'all_proxy'
  )

  foreach ($name in $proxyVars) {
    if (Test-Path "Env:$name") {
      Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    }
  }

  $noProxy = '127.0.0.1,localhost,10.0.2.2'
  $env:NO_PROXY = $noProxy
  $env:no_proxy = $noProxy
}

function Ensure-AdbReverse {
  param([int]$ApiPort)

  try {
    & adb reverse "tcp:$ApiPort" "tcp:$ApiPort" | Out-Null
    Write-Host "adb reverse tcp:$ApiPort tcp:$ApiPort"
  } catch {
    Write-Warning "adb reverse failed: $($_.Exception.Message)"
  }
}

function Get-ApiBaseUrl {
  param(
    [ValidateSet('auto', 'emulator', 'usb')]
    [string]$SelectedMode,
    [int]$ApiPort
  )

  $apiForEmulator = "http://10.0.2.2:$ApiPort/api/v1"
  $apiForUsb = "http://127.0.0.1:$ApiPort/api/v1"

  $adb = Get-Command adb -ErrorAction SilentlyContinue
  if (-not $adb) {
    if ($SelectedMode -eq 'emulator') {
      Write-Warning 'adb not found. Using emulator API URL without adb checks.'
      return $apiForEmulator
    }
    return $apiForUsb
  }

  $deviceLines = @(
    (& adb devices) |
      Select-Object -Skip 1 |
      Where-Object { $_ -match "`tdevice$" }
  )

  $hasAnyDevice = $deviceLines.Count -gt 0
  $hasEmulator = @($deviceLines | Where-Object { $_ -match '^emulator-' }).Count -gt 0

  if ($SelectedMode -eq 'emulator') {
    return $apiForEmulator
  }

  if ($SelectedMode -eq 'usb') {
    if ($hasAnyDevice) {
      Ensure-AdbReverse -ApiPort $ApiPort
    } else {
      Write-Warning 'No adb devices found. Continuing with localhost API URL.'
    }
    return $apiForUsb
  }

  if ($hasEmulator) {
    return $apiForEmulator
  }

  if ($hasAnyDevice) {
    Ensure-AdbReverse -ApiPort $ApiPort
  }

  return $apiForUsb
}

Push-Location $PSScriptRoot
try {
  Clear-ProxyEnv
  $apiBase = Get-ApiBaseUrl -SelectedMode $Mode -ApiPort $Port

  Write-Host "Mode: $Mode"
  Write-Host "API_BASE_URL: $apiBase"
  Write-Host "Working directory: $PSScriptRoot"

  if ($DryRun) {
    Write-Host 'Dry run enabled. Flutter command:'
    Write-Host "flutter run --dart-define=API_BASE_URL=$apiBase"
    exit 0
  }

  if (-not $SkipPubGet) {
    flutter pub get
  }

  flutter run --dart-define="API_BASE_URL=$apiBase"
} finally {
  Pop-Location
}
