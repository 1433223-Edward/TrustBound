#!/usr/bin/env bash
# Run manually only on the approved Ubuntu VM; installs no Docker or cloud resources.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run as root on the approved VM' >&2; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'Ubuntu 24.04 required' >&2; exit 1; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install -d -m 0755 /srv/trustbound
id trustbound-web >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin trustbound-web
id trustbound-deploy >/dev/null 2>&1 || useradd --system --create-home --home-dir /srv/trustbound/build-home --shell /usr/sbin/nologin trustbound-deploy
if [[ $(id -u trustbound-web) == 0 ]] || id -nG trustbound-web | tr ' ' '\n' | grep -Eq '^(docker|sudo|root)$'; then
    echo 'Web user must not have Docker or administrator identity' >&2; exit 1
fi
install -d -m 0755 /srv/trustbound
install -d -m 0755 -o trustbound-deploy -g trustbound-deploy /srv/trustbound/releases /srv/trustbound/pointers
install -d -m 0700 -o trustbound-web -g trustbound-web /var/lib/trustbound /var/lib/trustbound/evidence
install -d -m 0700 /etc/trustbound
if [[ ! -e /etc/trustbound/backend.env ]]; then
    install -m 0600 "$script_dir/backend.env.example" /etc/trustbound/backend.env
fi
install -m 0644 "$script_dir/trustbound-api.service" /etc/systemd/system/trustbound-api.service
systemctl daemon-reload
printf '%s\n' 'Directories/private unit prepared. No services started; public execution remains BLOCKED.'
