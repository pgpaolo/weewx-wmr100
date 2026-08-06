#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo "$0" "$@"
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl stop weewx 2>/dev/null || true
fi

"$ROOT_DIR/install-udev-rule.sh"

if command -v weectl >/dev/null 2>&1; then
    weectl extension install "$ROOT_DIR" --yes
elif command -v weewx_extension >/dev/null 2>&1; then
    weewx_extension --install="$ROOT_DIR"
else
    echo "ERROR: neither weectl nor weewx_extension was found." >&2
    exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl start weewx 2>/dev/null || true
fi

cat <<'EOF'

Extension installed.

Next step for WeeWX 5:
  sudo weectl station reconfigure --driver=user.wmr100

Set the physical model to WMR88 or WMR88A, then restart WeeWX.
Configuration examples are in examples/.
EOF
