#!/usr/bin/env bash
# Install the private Runner units without starting or restarting services.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run as root on the approved VM' >&2; exit 1; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for identity in trustbound-web trustbound-runner; do
    if [[ $(id -u "$identity") == 0 ]] || id -nG "$identity" | tr ' ' '\n' | grep -Eq '^(docker|sudo|root)$'; then
        echo "Unexpected privileged groups for $identity" >&2
        exit 1
    fi
done
[[ $(id -u trustbound-web) != "$(id -u trustbound-runner)" ]]
[[ -f /srv/trustbound/pointers/current/trustbound/runner_worker.py ]]
[[ $(stat -c '%U:%G %a' /var/lib/trustbound-runner) == 'trustbound-runner:trustbound-runner 700' ]]
[[ -S /run/user/$(id -u trustbound-runner)/docker.sock ]]

install -m 0644 "$script_dir/trustbound-runner.socket" "$script_dir/trustbound-runner.service" /etc/systemd/system/
install -d -m 0755 /etc/systemd/system/trustbound-api.service.d
install -m 0644 "$script_dir/runner-api.conf" /etc/systemd/system/trustbound-api.service.d/runner.conf
systemctl daemon-reload
printf '%s\n' 'Private Runner units installed. Start the socket and restart the private API when idle.'
