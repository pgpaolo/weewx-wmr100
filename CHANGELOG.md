# Changelog

All notable changes to this project are documented in this file.

## 3.5.6-gp6 — 2026-08-09

### Added

- Exposed the forecast code already transmitted by WMR100/WMR88/WMR88A pressure packets as the standard WeeWX `forecastIcon` observation.
- Added regression coverage proving that `forecastIcon` is emitted in the partial pressure LOOP packet.

### Preserved / Safety

- No changes to USB handling, timeout policy, recovery, framing, checksum validation, sensor decoding, rain calculations, or packet timing.
- `console_barometer` remains protocol/diagnostic metadata and is deliberately not mapped to WeeWX `barometer` or `altimeter`.
- `barometer` and `altimeter` remain software-derived by WeeWX `StdWXCalculate`, matching the WMR100 hardware model and avoiding archive semantics changes.
- All gp3/gp4/gp5 hardening and recovery fixes remain unchanged.

## 3.5.5-gp5 — 2026-08-07

### Fixed

- Added verified recovery for the rare `FF FF FF` frame-boundary condition observed on a real WMR88 trace.
- A single residual leading `0xFF` is removed only when the resulting packet has a known type, the documented length and a perfect checksum.
- Prevented the real WMR88 clock frame `ff b0 60 00 00 38 12 07 08 1a 00 83 01` from being discarded as a checksum error when the valid packet is `b0 60 00 00 38 12 07 08 1a 00 83 01`.

### Added

- Added `packet_leading_ff_recovered` developer-trace event with original/recovered frame, packet type, lengths and checksum details.
- Added `parser_leading_ff_recoveries` health/statistics counter.
- Added positive and negative regression tests based on the real WMR88 frame observed on 2026-08-07.

### Safety

- Recovery is deliberately conservative: arbitrary checksum failures are still rejected. The byte is stripped only when all type, length and checksum checks succeed.

## 3.5.4-gp4 — 2026-08-07

### Fixed

- Isolated WMR100/WMR88 USB polling timeouts remain informational and no longer set driver health to `degraded`.
- Driver health changes to `warning` only after `timeout_warning_threshold` consecutive timeouts.
- Soft reinitialisation and full reopen no longer report a prematurely healthy/ready state before data flow actually resumes.
- Added explicit `usb_read_recovered` events when normal USB reads resume after a timeout episode.

### Added

- Timeout episode identifiers and declared trace severities/classifications.
- Cumulative counters for timeout episodes, recoveries, warning episodes and maximum consecutive timeouts.
- Regression tests based on the real WMR88 timeout pattern observed on 2026-08-07.

## 3.5.3-gp3 — 2026-08-07

### Fixed

- Fixed WMR88/WMR88A startup frame synchronisation. The parser now waits for a real `FF FF` frame delimiter instead of potentially dropping a single leading status byte.
- Prevented valid `00 48 ...` wind frames from being misclassified as unknown packets such as `0x0c` when startup begins mid-frame.
- Added parser resynchronisation requests after USB recovery, command-only station reinitialisation, malformed HID reports and non-timeout USB read errors.
- Added regression coverage using the real WMR88 wind frame observed on 2026-08-07 (`00 48 0c 0c 13 30 01 00 20 c4 00`).

## 3.5.2-gp2 — 2026-08-06

### Added

- Explicit WMR88 and WMR88A model profiles.
- Model aliases such as `WMR-88`, `WMR-88A` and `WMR88/A`.
- Automatic WMR88/WMR88A live-data request command.
- Command-only USB reinitialisation before a complete reopen.
- Conservative WMR88 watchdog defaults appropriate for slow RF sensor intervals.
- Maximum remote-channel profile diagnostics.
- GitHub-ready WeeWX extension structure with `install.py`.
- Optional group-restricted udev rule and installer helpers.
- English and Italian documentation, configuration examples and testing guide.
- GitHub Actions regression-test workflow.
- JSONL trace summary utility and release-building script.

### Changed

- Promoted the WMR88/WMR88A family from generic compatibility to an explicitly configured operating profile.
- Default WMR88 timeout thresholds are warning `8`, soft reinitialisation `12`, full reopen `20` with a 15-second USB timeout.

## 3.5.1-gp1 — 2026-08-06

### Added

- Bounded packet buffering and stream resynchronisation.
- HID report validation.
- Packet checksum and length validation.
- Automatic USB reopen, re-enumeration, reclaim and reinitialisation.
- Rotating JSONL developer trace.
- Health and protocol counters.
- Unknown-packet and malformed-packet diagnostics.
- Optional live-data request command.

### Preserved

- Upstream WeeWX WMR100 sensor map.
- Upstream rain calculation behavior.
- Partial LOOP packet semantics.
- Existing unit systems and packet decoders.

## 3.5.0 — upstream base

- WeeWX WMR100 driver by Tom Keffer.
