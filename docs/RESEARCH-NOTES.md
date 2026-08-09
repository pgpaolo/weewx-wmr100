# WMR88 / WMR88A research notes

Initial protocol research performed on 2026-08-06 for 3.5.2-gp2; WMR88 real-world framing validation added on 2026-08-07 for 3.5.3-gp3.

## WeeWX hardware support

Official WeeWX hardware guide lists both WMR88 and WMR88A as USB/pyusb stations handled by the WMR100 driver:

- https://weewx.com/docs/5.0/hardware/drivers/
- https://weewx.com/docs/5.0/hardware/wmr100/

The WMR100 documentation also confirms that the station emits partial packets rather than one complete LOOP record.

## Oregon Scientific manual

WMR88/WMR88A user manual:

- https://asset.conrad.com/media10/add/160267/c1/-/en/000672191ML03/upute-za-rukovanje-672191-oregon-scientific-bezicna-profesionalna-usb-meteoroloska-stanica-wmr-88-5493-srebrna-siva.pdf

Relevant findings:

- WMR88 and WMR88A share the same weather-station functions and USB upload workflow.
- WMR88 uses DCF-77/MSF radio time; WMR88A uses WWVB.
- Up to three remote sensors can be active at one time.
- Listed optional sensors include THGR800, THGR810, UVN800 and THWR800.
- Wind transmission interval is approximately 56 seconds.
- Outdoor temperature/humidity transmission interval is approximately 102 seconds.
- USB upload starts after the cable is connected and the console displays the USB indicator.

## USB protocol and commands

Protocol description for WMR180, stated to be compatible with WMR100 and probably WMR88:

- https://wxtools.sourceforge.io/doc/wmr180.html

Commands:

- `20 00 08 01` — initialise station
- `01 D0 08 01` — request live data

The source advises reissuing the pair if no sensor data arrives for some minutes. It also confirms eight-byte HID reports, concatenated streams, `FF FF` delimiters, checksum calculation and the need to verify packet length because the checksum is weak.

A published Linux/Python test implementation used with a real WMR88 identifies the device as `0x0fde:0xca01` and sends both commands:

- https://habr.com/ru/articles/645491/

## WMR88 timing issue

Historical WeeWX user reports describe intermittent N/A values with short archive intervals. This is consistent with partial LOOP packets and the WMR88 sensor intervals, especially the approximately 102-second thermo-hygrometer interval:

- https://groups.google.com/g/weewx-user/c/scFzQZM5wsA

The driver does not fabricate or indefinitely cache readings. The recommended mitigation is a 300-second archive interval, while keeping the normal WeeWX partial-packet behaviour.

## Resulting engineering decisions

- Keep `[Station] station_type = WMR100` for WeeWX compatibility.
- Use `model = WMR88` or `model = WMR88A` for correct identification and profile defaults.
- Enable the live-data request by default for WMR88/WMR88A.
- Avoid full USB recovery before several minutes of consecutive silence.
- Reissue commands without closing the USB interface before attempting a full reopen.
- Preserve upstream packet decoding, units and rain increment semantics.
- Preserve partial LOOP packets to avoid repeating stale data or duplicating incremental rain.
