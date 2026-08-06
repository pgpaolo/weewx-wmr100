# Release 3.5.2-gp2

First GitHub-ready release of the hardened WMR100 protocol driver with a dedicated WMR88/WMR88A operating profile.

## Highlights

- automatic WMR88/WMR88A live-data request;
- staged recovery: warning, soft command reinitialisation, complete USB reopen;
- packet checksum and length validation;
- bounded stream parser and resynchronisation;
- rotating JSONL developer trace;
- standard WeeWX extension installer;
- optional secure udev rule;
- offline regression tests and GitHub Actions workflow;
- English and Italian installation documentation.

## Recommended initial settings

Use `model = WMR88` or `model = WMR88A`, keep `archive_interval = 300`, enable packet-level JSONL trace and leave raw USB report tracing disabled.

## Upgrade note

This extension installs `user.wmr100` and does not overwrite the WeeWX core driver. Reconfigure the station to use `driver = user.wmr100` after installation.
