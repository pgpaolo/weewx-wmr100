# Contributing

Contributions are welcome, especially traces from real WMR88 and WMR88A consoles.

Before opening a pull request:

1. Run `./scripts/run-tests.sh`.
2. Keep meteorological behavior backward compatible unless a protocol trace proves a correction is necessary.
3. Do not include personal data, public IP addresses, station coordinates or complete production configuration files in traces.
4. For parser changes, include a minimal sanitized packet sample and a regression test.
5. Update `CHANGELOG.md` when behavior changes.

For a hardware issue, include:

- console model;
- WeeWX version and installation method;
- operating system and architecture;
- `lsusb -d 0fde:ca01` output;
- relevant journal lines;
- a short sanitized JSONL trace captured with raw reports disabled first.
