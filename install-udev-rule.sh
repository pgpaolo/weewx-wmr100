#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    exec sudo "$0" "$@"
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE_RULE="$SCRIPT_DIR/util/udev/rules.d/60-weewx-wmr100.rules"
DEST_RULE="/etc/udev/rules.d/60-weewx-wmr100.rules"
WEEWX_GROUP=${WEEWX_GROUP:-weewx}

if ! command -v udevadm >/dev/null 2>&1; then
    echo "ERROR: udevadm not found; this helper is for Linux systems using udev." >&2
    exit 1
fi

if ! getent group "$WEEWX_GROUP" >/dev/null 2>&1; then
    echo "ERROR: group '$WEEWX_GROUP' does not exist." >&2
    echo "Set WEEWX_GROUP to the group used by the WeeWX service." >&2
    exit 1
fi

TMP_RULE=$(mktemp)
trap 'rm -f "$TMP_RULE"' EXIT HUP INT TERM
sed "s/GROUP:=\"weewx\"/GROUP:=\"$WEEWX_GROUP\"/" "$SOURCE_RULE" > "$TMP_RULE"
install -o root -g root -m 0644 "$TMP_RULE" "$DEST_RULE"
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --attr-match=idVendor=0fde --attr-match=idProduct=ca01 || true

echo "Installed $DEST_RULE for group $WEEWX_GROUP."
echo "Reconnect the WMR console USB cable, then restart WeeWX."
