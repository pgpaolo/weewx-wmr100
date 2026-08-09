# Copyright (c) 2026 GP
# Licensed under the GNU General Public License v3.0 or later.

from weecfg.extension import ExtensionInstaller


def loader():
    return WMR100WMR88Installer()


class WMR100WMR88Installer(ExtensionInstaller):
    """WeeWX extension installer for the hardened WMR100 protocol driver."""

    def __init__(self):
        super(WMR100WMR88Installer, self).__init__(
            version='3.5.6-gp6',
            name='wmr100-wmr88-hardened',
            description=(
                'Hardened WeeWX USB driver for Oregon Scientific '
                'WMR100/WMR100N, WMR88/WMR88A, WMR180/WMR180A and WMRS200'
            ),
            author='Tom Keffer; GP hardening and diagnostics',
            files=[
                ('bin/user', ['bin/user/wmr100.py']),
            ],
        )
