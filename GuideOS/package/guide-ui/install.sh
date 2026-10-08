#!/bin/sh
# Stage-only installer: does not replace, enable or restart the Guide shell.
set -eu
test "$#" = 2 && test "$1" = --root || {
    echo "Usage: install.sh --root /path/to/staged-root" >&2
    exit 2
}
root=$(realpath -- "$2")
test "$root" != /
test -d "$root/usr/lib/guideos/shell0"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d -m755 "$root/usr/lib/guideos/ui" "$root/usr/share/guideos/ui"
install -m644 "$here/guide_ui.py" "$here/guide_shell_schema_adapter.py" "$here/guide_ui_text.py" "$here/guide_field_ui.py" \
    "$root/usr/lib/guideos/ui/"
install -m644 "$here/tokens.toml" "$here/components.toml" \
    "$root/usr/share/guideos/ui/"
install -d -m755 "$root/usr/share/guideos/ui/field-1"
install -m644 "$here/field-1/tokens.toml" "$here/field-1/components.toml" "$root/usr/share/guideos/ui/field-1/"
echo GUIDE_UI_HANDOFF_STAGED_NO_SHELL_CHANGE
