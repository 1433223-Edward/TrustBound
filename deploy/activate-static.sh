#!/usr/bin/env bash
# Atomic static release switch only; this script never enables public API execution.
set -euo pipefail
[[ $(id -un) == trustbound-deploy ]] || exit 1
commit=${1:?full commit SHA required}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || exit 1
base=/srv/trustbound/pointers
target=/srv/trustbound/releases/$commit
[[ -f $target/frontend/dist/index.html && $(cat "$target/RELEASE_COMMIT") == "$commit" ]] || exit 1
if [[ -L $base/current ]]; then
    old=$(readlink -f "$base/current")
    [[ $old =~ ^/srv/trustbound/releases/[0-9a-f]{40}$ ]] || exit 1
    if [[ $old == "$target" ]]; then
        echo "Static release already active; previous release preserved"
        exit 0
    fi
    ln -s -- "$old" "$base/.previous-$$"
    mv -Tf -- "$base/.previous-$$" "$base/previous"
fi
ln -s -- "$target" "$base/.current-$$"
mv -Tf -- "$base/.current-$$" "$base/current"
printf '%s\n' "Static release active: $commit. Restart private API separately only when idle."
