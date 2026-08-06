#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m py_compile "$ROOT_DIR/bin/user/wmr100.py" "$ROOT_DIR/install.py"
python3 "$ROOT_DIR/tests/test_wmr100.py"
python3 "$ROOT_DIR/tests/test_install.py"

for script in \
    "$ROOT_DIR/install.sh" \
    "$ROOT_DIR/install-udev-rule.sh" \
    "$ROOT_DIR/uninstall-udev-rule.sh" \
    "$ROOT_DIR/scripts/build-release.sh"; do
    bash -n "$script"
done

echo "Repository validation passed."
