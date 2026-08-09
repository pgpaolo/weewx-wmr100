# Hardened WeeWX driver for WMR100 / WMR88

[![Tests](https://github.com/OWNER/weewx-wmr100-wmr88-hardened/actions/workflows/tests.yml/badge.svg)](https://github.com/OWNER/weewx-wmr100-wmr88-hardened/actions/workflows/tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.txt)

Hardened WeeWX USB driver for Oregon Scientific stations that expose the WMR100 low-speed HID protocol, with an explicit operating profile for **WMR88 and WMR88A**.

This repository is based on the WeeWX `wmr100.py` driver version `3.5.0`. Release `3.5.6-gp6` preserves the upstream meteorological mapping while adding USB recovery, packet validation, parser resynchronisation, model-aware WMR88 initialization and a rotating JSONL developer trace.

> **Validation status:** automated protocol and recovery tests pass. Long-duration testing with real WMR88/WMR88A hardware is still recommended before unattended production use.

Italian documentation: [README-IT.md](README-IT.md)

## Supported consoles

| Console | Profile | Notes |
|---|---|---|
| WMR88 / WMR88A | Primary | Live-data request enabled automatically; conservative watchdog |
| WMR100 / WMR100N | Supported | Upstream-compatible initialization by default |
| WMR180 / WMR180A | Supported | Same live-data request profile as WMR88 |
| WMRS200 | Supported when using the WMR100 USB HID interface | No console altitude setting |

The WMR200/WMR200A requires a different driver. WMR89/WMR89A must not be assumed compatible merely because they can use similar Oregon Scientific RF sensors.

## Common sensors

The WMR88/WMR88A family commonly uses:

- WGR800 or equivalent wind sensor;
- PCR800 or equivalent rain gauge;
- THGR800 / THGR810 temperature and humidity sensors;
- THWR800 temperature-only sensor;
- UVN800 UV sensor;
- up to three remote sensor channels in the WMR88 profile.

## Main improvements

- Exposes the forecast code sent natively by the console pressure packet as the standard WeeWX `forecastIcon` observation.
- Keeps WMR100 `barometer` and `altimeter` software-calculated by `StdWXCalculate`; the console relative-pressure value remains diagnostic-only.
- Recovers a verified WMR88/WMR100 frame when a single residual leading `0xFF` is left at an `FF FF FF` boundary.
- Keeps isolated USB polling timeouts informational; health changes only when the configured warning threshold is reached.
- Emits `usb_read_recovered` when USB reads resume after a timeout episode.
- Distinguishes ordinary USB polling timeouts from real I/O failures.
- Re-sends initialization commands before performing a full USB reopen.
- Releases, re-enumerates, reclaims and reinitializes the USB interface after prolonged silence.
- Validates 8-byte HID reports and their declared payload size.
- Bounds the packet buffer and resynchronizes on `FF FF` framing.
- Verifies both checksum and expected packet length.
- Traces malformed, unknown and suspicious packets without stopping acquisition.
- Provides rotating JSONL developer diagnostics and health counters.
- Keeps the upstream partial LOOP packet behavior to avoid repeating stale data or duplicating incremental rain.

## Requirements

- WeeWX 5.x recommended; the extension layout is also compatible with the legacy WeeWX 4 extension installer.
- Python version supported by the installed WeeWX release.
- USB support already required by the standard WeeWX WMR100 driver.
- Linux access to USB device `0fde:ca01`.

## Installation from GitHub — WeeWX 5

After publishing this directory as a GitHub repository, replace `OWNER` below with the GitHub account or organization name:

```bash
sudo weectl extension install \
  https://github.com/OWNER/weewx-wmr100-wmr88-hardened/archive/refs/heads/main.zip
```

Install or refresh the optional USB permission rule:

```bash
git clone https://github.com/OWNER/weewx-wmr100-wmr88-hardened.git
cd weewx-wmr100-wmr88-hardened
sudo ./install-udev-rule.sh
```

Then configure the station:

```bash
sudo weectl station reconfigure --driver=user.wmr100
```

Select or enter `WMR88` for the European/UK console, or `WMR88A` for the North American console. Restart WeeWX:

```bash
sudo systemctl restart weewx
sudo journalctl -u weewx -n 100 --no-pager
```

## Installation from a release ZIP — WeeWX 5

```bash
unzip weewx-wmr100-wmr88-hardened-3.5.6-gp6.zip
cd weewx-wmr100-wmr88-hardened-3.5.6-gp6
sudo ./install-udev-rule.sh
sudo weectl extension install . --yes
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
```

The helper below installs the udev rule and the WeeWX extension, but intentionally leaves station reconfiguration interactive:

```bash
sudo ./install.sh
```

## WeeWX 4

```bash
sudo ./install-udev-rule.sh
sudo weewx_extension --install=.
sudo wee_config --reconfigure --driver=user.wmr100 --no-prompt
sudo systemctl restart weewx
```

## Recommended WMR88 configuration

```ini
[Station]
    station_type = WMR100

[WMR100]
    driver = user.wmr100
    model = WMR88

    vendor_id = 0x0fde
    product_id = 0xca01
    interface = 0
    IN_endpoint = 0x81

    timeout = 15
    wait_before_retry = 5
    max_tries = 3
    recovery_max_tries = 3

    timeout_warning_threshold = 8
    timeout_reinit_threshold = 12
    timeout_recovery_threshold = 20

    send_data_request = true
    command_delay = 0.05
    max_remote_channels = 3

    strict_packet_lengths = true
    max_packet_length = 64

    developer_trace = true
    developer_trace_path = /var/log/weewx/wmr100-developer-trace.jsonl
    developer_trace_max_bytes = 5242880
    developer_trace_backup_count = 5
    developer_trace_raw_reports = false
    developer_trace_packets = true

    stats_log_interval = 3600

[StdArchive]
    archive_interval = 300
```

The WMR88 model profile automatically enables `send_data_request` and the conservative watchdog values unless explicitly overridden.

## USB permission check

```bash
lsusb -d 0fde:ca01
BUS=$(lsusb -d 0fde:ca01 | awk '{print $2}')
DEV=$(lsusb -d 0fde:ca01 | awk '{print substr($4,1,3)}')
ls -l "/dev/bus/usb/$BUS/$DEV"
```

The WeeWX service account must have read/write access. Package-based WeeWX 5 installations may already provide suitable udev rules for supported core hardware; the included rule is therefore optional when permissions are already correct.

## Developer trace

```bash
sudo install -d -o weewx -g weewx -m 0750 /var/log/weewx
sudo touch /var/log/weewx/wmr100-developer-trace.jsonl
sudo chown weewx:weewx /var/log/weewx/wmr100-developer-trace.jsonl
sudo chmod 0640 /var/log/weewx/wmr100-developer-trace.jsonl
```

Follow the trace:

```bash
sudo tail -f /var/log/weewx/wmr100-developer-trace.jsonl
```

Generate a summary:

```bash
sudo python3 tools/trace-summary.py \
  /var/log/weewx/wmr100-developer-trace.jsonl
```

Keep `developer_trace_raw_reports = false` for normal operation. Raw HID reports should be enabled only for short diagnostic captures.

## Verification

```bash
sudo journalctl -u weewx -f
```

Expected startup entry:

```text
WMR100 driver version is 3.5.6-gp6
```

Run repository tests without a physical station:

```bash
python3 tests/test_wmr100.py
python3 tests/test_install.py
```

Or:

```bash
./scripts/run-tests.sh
```

## Updating

```bash
sudo systemctl stop weewx
sudo weectl extension install . --yes
sudo systemctl start weewx
```

The extension installer replaces `bin/user/wmr100.py`. Back up `weewx.conf` before changing station configuration.

## Uninstalling

```bash
sudo weectl extension uninstall wmr100-wmr88-hardened --yes
sudo systemctl restart weewx
```

To remove the optional udev rule as well:

```bash
sudo ./uninstall-udev-rule.sh
```

## Important operational notes

- Sensor RF intervals are not USB polling intervals. A missing sensor packet does not by itself prove that the USB link failed.
- LOOP packets remain partial by design. WeeWX accumulates them for archive generation.
- Do not map diagnostic fields into the archive schema without adding the corresponding database columns.
- Preserve a copy of the original driver and configuration during initial field validation.

## Repository layout

```text
bin/user/wmr100.py          WeeWX driver
install.py                  WeeWX ExtensionInstaller metadata
examples/                   ready-to-copy configuration examples
util/udev/rules.d/          optional USB permission rule
docs/                       configuration, testing and research notes
tests/                      offline regression tests
tools/trace-summary.py      JSONL diagnostic summary
scripts/build-release.sh    deterministic release archive builder
GITHUB-PUBLISH-IT.md        step-by-step GitHub publishing guide
```

## License and attribution

Distributed under the GNU General Public License version 3 or later. The upstream copyright notice from Tom Keffer is preserved in the driver. See [LICENSE.txt](LICENSE.txt) and [NOTICE.md](NOTICE.md).
