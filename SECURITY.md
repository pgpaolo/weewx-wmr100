# Security policy

Report vulnerabilities privately to the repository maintainer rather than publishing exploit details in an issue.

Do not attach unredacted `weewx.conf`, system debug bundles or traces containing credentials, private URLs, station coordinates, usernames or network addresses.

The included udev rule grants read/write access only to the configured WeeWX group and does not use mode `0666`.
