# Release 3.5.4-gp4

## WMR88/WMR88A timeout health-state fix

This release refines USB timeout telemetry after analysis of a real WMR88 developer trace. The station produced many isolated 15-second interrupt-read timeouts, but every episode recovered naturally and never approached the configured WMR88 warning/reinitialisation/recovery thresholds.

### Fixed

- Isolated USB polling timeouts no longer change driver health to `degraded`.
- Health remains unchanged for timeout counts below `timeout_warning_threshold`.
- Health changes to `warning` only when the configured warning threshold is reached.
- A successful soft reinitialisation remains in `warning` until an actual USB read confirms that data flow resumed.
- A full USB reopen remains `recovering` until a subsequent valid read/payload confirms recovery.
- A successful USB read after one or more timeouts emits an explicit `usb_read_recovered` trace event.
- Recovery events include the timeout episode number, recovered timeout count, total timeout count, recovery latency and time since the previous successful payload.
- Timeout events now include a declared severity (`info`, `warning` or `error`) and a classification suitable for the universal developer dashboard.

### Added diagnostics

New cumulative statistics:

- `usb_timeout_episodes`
- `usb_timeout_recoveries`
- `usb_timeout_warning_episodes`
- `usb_timeout_max_consecutive`

### Preserved

- WMR88/WMR88A warning threshold: 8 consecutive timeouts.
- Soft reinitialisation threshold: 12 consecutive timeouts.
- Full USB recovery threshold: 20 consecutive timeouts.
- WMR100/WMR88 packet decoding, framing, checksum rules and meteorological output are unchanged.
- The 3.5.3-gp3 WMR88 frame-synchronisation fix remains intact.

### Regression tests

Tests now verify that:

1. a single timeout followed by a successful report stays healthy and produces `usb_read_recovered`;
2. health moves to `warning` only at the configured warning threshold;
3. recovery returns health to `healthy`;
4. the existing WMR88 soft reinitialisation and full USB reopen logic still work.
