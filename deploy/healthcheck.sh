#!/usr/bin/env bash
# No POST, no model invocation and no Docker changes.
set -euo pipefail
if [[ ${1:-} == --public-static ]]; then
    domain=${2:?domain required}
    [[ $domain =~ ^[a-zA-Z0-9.-]+$ && $domain != -* ]] || exit 1
    curl --fail --silent --show-error --max-time 10 "https://$domain/" >/dev/null
    code=$(curl --silent --show-error --max-time 10 -o /dev/null -w '%{http_code}' "https://$domain/api/health")
    [[ $code == 503 ]] || { echo 'Public API guard not confirmed' >&2; exit 1; }
    echo 'Static HTTPS healthy; execution intentionally BLOCKED'
else
    curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/api/health
fi
