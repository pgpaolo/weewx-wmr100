# Release 3.5.5-gp5 — Verified Leading-FF Frame Recovery

This release fixes a rare WMR88 framing edge case discovered from a real developer trace.

## What was observed

Immediately after startup the trace contained:

```text
ff b0 60 00 00 38 12 07 08 1a 00 83 01
```

As a 13-byte frame this fails checksum and appears to have packet type `0xb0`. Removing exactly the residual leading `0xff` produces:

```text
b0 60 00 00 38 12 07 08 1a 00 83 01
```

This is a valid 12-byte WMR100-family clock packet (`0x60`) whose checksum is exactly `0x0183`.

## Fix

The parser now attempts a one-byte leading-FF recovery only after the original checksum fails, and only when all of these checks pass:

1. the original frame begins with `0xff`;
2. removing exactly one byte exposes a known packet type;
3. the recovered frame has the documented packet length;
4. the recovered checksum is exact.

If any check fails, the existing checksum-error path is used unchanged.

## Diagnostics

Successful recovery emits:

```text
packet_leading_ff_recovered
```

with original and recovered frame hex, packet type/name, lengths and checksum values. A new `parser_leading_ff_recoveries` counter is included in health statistics.

## Compatibility

No meteorological mapping, unit conversion, USB timeout threshold or normal frame format has changed. The gp4 timeout-health fixes and gp3 startup synchronization fix are preserved.
