param(
  [ValidateSet('auto', 'emulator', 'usb')]
  [string]$Mode = 'auto',
  [int]$Port = 8000,
  [string]$ApiBaseUrl,
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

function Resolve-AdbPath {
  $adbCmd = Get-Command adb -ErrorAction SilentlyContinue
  if ($adbCmd -and $adbCmd.Source) {
    return $adbCmd.Source
  }

  $candidates = @(
    (Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'),
    (Join-Path $env:USERPROFILE 'AppData\Local\Android\Sdk\platform-tools\adb.exe')
  )

  if ($env:ANDROID_SDK_ROOT) {
    $candidates += (Join-Path $env:ANDROID_SDK_ROOT 'platform-tools\adb.exe')
  }

  if ($env:ANDROID_HOME) {
    $candidates += (Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe')
  }

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      return $candidate
    }
  }

  return $null
}

function Ensure-AdbReverse {
  param(
    [int]$ApiPort,
    [string]$AdbPath
  )

  try {
    & $AdbPath reverse "tcp:$ApiPort" "tcp:$ApiPort" | Out-Null
    Write-Host "adb reverse tcp:$ApiPort tcp:$ApiPort"
  } catch {
    Write-Warning "adb reverse failed: $($_.Exception.Message)"
  }
}

function Get-HostLanIp {
  try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
      Where-Object {
        $_.IPAddress -notlike '127.*' -and
        $_.IPAddress -notlike '169.254.*' -and
        $_.IPAddress -ne '0.0.0.0'
      } |
      Select-Object -ExpandProperty IPAddress

    $scored = @()
    foreach ($ip in $ips) {
      $score = 50
      if ($ip -match '^192\.168\.') {
        $score = 1
      } elseif ($ip -match '^10\.') {
        $score = 2
      } elseif ($ip -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.') {
        $score = 3
      }

      $scored += [pscustomobject]@{
        IP    = $ip
        Score = $score
      }
    }

    if ($scored.Count -gt 0) {
      $best = $scored | Sort-Object Score, IP | Select-Object -First 1
      return $best.IP
    }
  } catch {
    # Ignore and fallback to default URL strategy.
  }

  return $null
}

function Get-ApiBaseUrl {
  param(
    [ValidateSet('auto', 'emulator', 'usb')]
    [string]$SelectedMode,
    [int]$ApiPort,
    [string]$ExplicitApiBaseUrl,
    [string]$AdbPath
  )

  if ($ExplicitApiBaseUrl) {
    $normalized = $ExplicitApiBaseUrl.Trim()
    if ($normalized.EndsWith('/')) {
      $normalized = $normalized.TrimEnd('/')
    }
    return $normalized
  }

  $apiForEmulator = "http://10.0.2.2:$ApiPort/api/v1"
  $apiForUsb = "http://127.0.0.1:$ApiPort/api/v1"

  if (-not $AdbPath) {
    if ($SelectedMode -eq 'emulator') {
      Write-Warning 'adb not found. Using emulator API URL without adb checks.'
      return $apiForEmulator
    }

    $lanIp = Get-HostLanIp
    if ($lanIp) {
      $apiForLan = "http://${lanIp}:$ApiPort/api/v1"
      Write-Warning "adb not found. Using LAN API URL: $apiForLan"
      Write-Warning 'Ensure phone and computer are on the same Wi-Fi network.'
      return $apiForLan
    }

    Write-Warning 'adb not found and LAN IP detection failed. Falling back to localhost API URL.'
    return $apiForUsb
  }

  $deviceLines = @(
    (& $AdbPath devices) |
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
      Ensure-AdbReverse -ApiPort $ApiPort -AdbPath $AdbPath
    } else {
      Write-Warning 'No adb devices found. Continuing with localhost API URL.'
    }
    return $apiForUsb
  }

  if ($hasEmulator) {
    return $apiForEmulator
  }

  if ($hasAnyDevice) {
    Ensure-AdbReverse -ApiPort $ApiPort -AdbPath $AdbPath
  }

  return $apiForUsb
}

Push-Location $PSScriptRoot
try {
  Clear-ProxyEnv
  $adbPath = Resolve-AdbPath
  if ($adbPath) {
    Write-Host "ADB: $adbPath"
  } else {
    Write-Warning 'adb was not found in PATH or standard Android SDK locations.'
  }

  $apiBase = Get-ApiBaseUrl -SelectedMode $Mode -ApiPort $Port -ExplicitApiBaseUrl $ApiBaseUrl -AdbPath $adbPath

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
