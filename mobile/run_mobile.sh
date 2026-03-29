#!/usr/bin/env bash
set -euo pipefail

MODE="auto"
PORT="8000"
SKIP_PUB_GET=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: run_mobile.sh [options]

Options:
  --mode <auto|emulator|usb>   Device mode (default: auto)
  --port <number>              Backend API port (default: 8000)
  --skip-pub-get               Skip flutter pub get
  --dry-run                    Print flutter command without running
  -h, --help                   Show this help message
EOF
}

warn() {
  printf 'Warning: %s\n' "$1" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --mode\n' >&2
        usage
        exit 1
      fi
      MODE="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        printf 'Missing value for --port\n' >&2
        usage
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    --skip-pub-get)
      SKIP_PUB_GET=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  auto|emulator|usb) ;;
  *)
    printf 'Invalid mode: %s\n' "$MODE" >&2
    usage
    exit 1
    ;;
esac

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  printf 'Invalid port: %s\n' "$PORT" >&2
  exit 1
fi

clear_proxy_env() {
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
  local no_proxy_value="127.0.0.1,localhost,10.0.2.2"
  export NO_PROXY="$no_proxy_value"
  export no_proxy="$no_proxy_value"
}

ensure_adb_reverse() {
  local api_port="$1"
  if adb reverse "tcp:${api_port}" "tcp:${api_port}" >/dev/null 2>&1; then
    printf 'adb reverse tcp:%s tcp:%s\n' "$api_port" "$api_port"
  else
    warn "adb reverse failed"
  fi
}

get_api_base_url() {
  local selected_mode="$1"
  local api_port="$2"

  local api_for_emulator="http://10.0.2.2:${api_port}/api/v1"
  local api_for_usb="http://127.0.0.1:${api_port}/api/v1"

  if ! command -v adb >/dev/null 2>&1; then
    if [[ "$selected_mode" == "emulator" ]]; then
      warn "adb not found. Using emulator API URL without adb checks."
      printf '%s\n' "$api_for_emulator"
      return
    fi
    printf '%s\n' "$api_for_usb"
    return
  fi

  local device_lines
  device_lines="$(adb devices | tail -n +2 | grep -E '[[:space:]]device$' || true)"

  local has_any_device=0
  local has_emulator=0
  if [[ -n "$device_lines" ]]; then
    has_any_device=1
    if printf '%s\n' "$device_lines" | grep -q '^emulator-'; then
      has_emulator=1
    fi
  fi

  if [[ "$selected_mode" == "emulator" ]]; then
    printf '%s\n' "$api_for_emulator"
    return
  fi

  if [[ "$selected_mode" == "usb" ]]; then
    if [[ $has_any_device -eq 1 ]]; then
      ensure_adb_reverse "$api_port"
    else
      warn "No adb devices found. Continuing with localhost API URL."
    fi
    printf '%s\n' "$api_for_usb"
    return
  fi

  if [[ $has_emulator -eq 1 ]]; then
    printf '%s\n' "$api_for_emulator"
    return
  fi

  if [[ $has_any_device -eq 1 ]]; then
    ensure_adb_reverse "$api_port"
  fi

  printf '%s\n' "$api_for_usb"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

clear_proxy_env
API_BASE_URL="$(get_api_base_url "$MODE" "$PORT")"

printf 'Mode: %s\n' "$MODE"
printf 'API_BASE_URL: %s\n' "$API_BASE_URL"
printf 'Working directory: %s\n' "$SCRIPT_DIR"

if [[ $DRY_RUN -eq 1 ]]; then
  printf 'Dry run enabled. Flutter command:\n'
  printf 'flutter run --dart-define=API_BASE_URL=%s\n' "$API_BASE_URL"
  exit 0
fi

cd "$SCRIPT_DIR"

if [[ $SKIP_PUB_GET -eq 0 ]]; then
  flutter pub get
fi

flutter run --dart-define="API_BASE_URL=${API_BASE_URL}"
