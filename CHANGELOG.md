# Changelog

All notable changes to this project are documented in this file.

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
