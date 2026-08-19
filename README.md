# Hardened WeeWX driver for WMR100 / WMR88

[![Tests](https://github.com/pgpaolo/weewx-wmr100/actions/workflows/tests.yml/badge.svg)](https://github.com/pgpaolo/weewx-wmr100/actions/workflows/tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.txt)

Hardened WeeWX USB driver for Oregon Scientific consoles that expose the WMR100 low-speed HID protocol, with an explicit operating profile for **WMR88 / WMR88A**.

Current release: **3.5.6-gp6**.

The driver preserves the upstream meteorological mapping while adding staged USB recovery, packet validation, parser resynchronisation, model-aware WMR88 initialization and rotating JSONL developer diagnostics.

Italian documentation: [README-IT.md](README-IT.md)

## Supported consoles

| Console | Status | Notes |
|---|---|---|
| WMR88 / WMR88A | Primary profile | Live-data request enabled automatically; conservative watchdog |
| WMR100 / WMR100N | Supported | Upstream-compatible initialization |
| WMR180 / WMR180A | Supported | Uses the live-data request profile |
| WMRS200 | Supported when exposing the WMR100 USB HID interface | No console altitude setting |

**WMR200/WMR200A requires a different driver.** WMR89/WMR89A should not be assumed compatible only because they use similar Oregon Scientific RF sensors.

## Main improvements

- exposes the native console forecast code as WeeWX `forecastIcon`;
- keeps `barometer` and `altimeter` under `StdWXCalculate` control;
- validates HID report size, packet length and checksum;
- resynchronizes on `FF FF` framing and recovers a verified residual `0xFF` case;
- distinguishes ordinary polling timeouts from real USB I/O failures;
- re-sends initialization commands before a full USB reopen;
- re-enumerates, reclaims and reinitializes the USB interface after prolonged silence;
- traces malformed, unknown and suspicious packets without stopping acquisition;
- provides rotating JSONL diagnostics and health counters;
- preserves partial LOOP packet behaviour to avoid stale data and duplicated incremental rain.

## Requirements

- WeeWX 5.x recommended; legacy WeeWX 4 extension installation is also supported;
- Python supported by the installed WeeWX release;
- Linux USB access to device `0fde:ca01`;
- standard WeeWX USB dependencies for WMR100-family hardware.

## Install from GitHub — WeeWX 5

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/heads/main.zip
```

Optional USB permission helper:

```bash
git clone https://github.com/pgpaolo/weewx-wmr100.git
cd weewx-wmr100
sudo ./install-udev-rule.sh
```

Configure the station:

```bash
sudo weectl station reconfigure --driver=user.wmr100
sudo systemctl restart weewx
sudo journalctl -u weewx -n 100 --no-pager
```

Select `WMR88` for the European/UK console or `WMR88A` for the North American variant.

## Install a tagged release

```bash
sudo weectl extension install \
  https://github.com/pgpaolo/weewx-wmr100/archive/refs/tags/v3.5.6-gp6.zip
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

## Developer trace

Prepare the trace file:

```bash
sudo install -d -o weewx -g weewx -m 0750 /var/log/weewx
sudo touch /var/log/weewx/wmr100-developer-trace.jsonl
sudo chown weewx:weewx /var/log/weewx/wmr100-developer-trace.jsonl
sudo chmod 0640 /var/log/weewx/wmr100-developer-trace.jsonl
```

Follow it:

```bash
sudo tail -f /var/log/weewx/wmr100-developer-trace.jsonl
```

Summarize it:

```bash
sudo python3 tools/trace-summary.py /var/log/weewx/wmr100-developer-trace.jsonl
```

Keep `developer_trace_raw_reports = false` during normal operation.

## Verification and tests

Expected startup entry:

```text
WMR100 driver version is 3.5.6-gp6
```

Run the complete offline validation suite:

```bash
./scripts/run-tests.sh
```

GitHub Actions runs the same validation automatically on pull requests and pushes to `main`.

## USB permission check

```bash
lsusb -d 0fde:ca01
BUS=$(lsusb -d 0fde:ca01 | awk '{print $2}')
DEV=$(lsusb -d 0fde:ca01 | awk '{print substr($4,1,3)}')
ls -l "/dev/bus/usb/$BUS/$DEV"
```

The WeeWX service account must have read/write access to the device.

## Important operational notes

- Sensor RF intervals are not USB polling intervals.
- LOOP packets remain partial by design; WeeWX accumulates them for archive generation.
- Do not map diagnostic fields into the archive schema without adding the corresponding database columns.
- Back up `weewx.conf` before changing station configuration.
- Never commit local `weewx.conf`, JSONL traces, log files, credentials, private URLs or local network details.

## Repository layout

```text
bin/user/wmr100.py          WeeWX driver
install.py                  ExtensionInstaller metadata
examples/                   configuration examples
util/udev/rules.d/          optional USB permission rule
docs/                       configuration, testing and research notes
tests/                      offline regression tests
tools/trace-summary.py      JSONL diagnostic summary
scripts/run-tests.sh        repository validation suite
scripts/build-release.sh    deterministic release archive builder
```

## License and attribution

Distributed under the GNU General Public License version 3 or later. Upstream WeeWX copyright notices are preserved in the driver.

See [LICENSE.txt](LICENSE.txt), [NOTICE.md](NOTICE.md), [SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
