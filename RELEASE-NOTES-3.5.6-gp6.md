# Release 3.5.6-gp6 — Native Console Forecast Icon Support

This is a deliberately small, production-oriented release.

## Added

- The native forecast code carried by the WMR100/WMR88/WMR88A pressure packet (`0x46`) is now exposed as WeeWX `forecastIcon`.
- This allows skins and services that understand `forecastIcon` to use the console forecast directly, as with the WMR200 family.

## Stability policy

No USB, parser, recovery, timeout, checksum, framing, sensor-decoding, unit, rain, or packet-timing logic was changed.

The second pressure value decoded as `console_barometer` is intentionally kept internal/diagnostic. It is **not** mapped to `barometer` or `altimeter`. For the WMR100 family, WeeWX `StdWXCalculate` remains responsible for software-derived barometer and altimeter values using station metadata such as altitude.

## Upgrade

The existing `[WMR100]` configuration can be kept unchanged. Restart WeeWX after replacing/installing the driver and confirm:

```text
WMR100 driver version is 3.5.6-gp6
```

When a pressure packet is received, the driver LOOP packet can now include:

```text
pressure
forecastIcon
```

All previous gp3/gp4/gp5 stability fixes remain intact.
