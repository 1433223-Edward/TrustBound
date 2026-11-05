#!/usr/bin/env bash
# Swap back only to a previously prepared immutable release.
set -euo pipefail
previous=$(readlink -f /srv/trustbound/pointers/previous)
[[ $previous =~ ^/srv/trustbound/releases/([0-9a-f]{40})$ ]] || exit 1
commit=${BASH_REMATCH[1]}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$script_dir/activate-static.sh" "$commit"
