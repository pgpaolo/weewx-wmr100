#!/usr/bin/env python3
"""Validate install.py without requiring a WeeWX installation."""

from pathlib import Path
import importlib.util
import sys
import types


class ExtensionInstaller(dict):
    def __init__(self, **kwargs):
        super().__init__(kwargs)


weecfg = types.ModuleType('weecfg')
weecfg_extension = types.ModuleType('weecfg.extension')
weecfg_extension.ExtensionInstaller = ExtensionInstaller
weecfg.extension = weecfg_extension
sys.modules['weecfg'] = weecfg
sys.modules['weecfg.extension'] = weecfg_extension

install_path = Path(__file__).resolve().parents[1] / 'install.py'
spec = importlib.util.spec_from_file_location('wmr100_install', install_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
installer = module.loader()

assert installer['version'] == '3.5.2-gp2'
assert installer['name'] == 'wmr100-wmr88-hardened'
assert installer['files'] == [('bin/user', ['bin/user/wmr100.py'])]
assert (install_path.parent / 'bin' / 'user' / 'wmr100.py').is_file()

print('Extension installer metadata test passed.')
