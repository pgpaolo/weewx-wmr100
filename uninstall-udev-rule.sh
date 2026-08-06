#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    exec sudo "$0" "$@"
fi

DEST_RULE="/etc/udev/rules.d/60-weewx-wmr100.rules"
rm -f "$DEST_RULE"
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=usb --attr-match=idVendor=0fde --attr-match=idProduct=ca01 || true
fi

echo "Removed $DEST_RULE. Reconnect the console if necessary."
