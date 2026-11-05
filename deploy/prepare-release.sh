#!/usr/bin/env bash
# Build a reviewed committed release as trustbound-deploy, never as the Web identity.
set -euo pipefail
[[ $(id -un) == trustbound-deploy ]] || { echo 'Run as trustbound-deploy' >&2; exit 1; }
repo=${1:?usage: prepare-release.sh REPOSITORY FULL_COMMIT_SHA}
commit=${2:?full 40-character commit SHA required}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ $(git -C "$repo" rev-parse "$commit^{commit}") == "$commit" ]] || exit 1
for required in trustbound/api.py trustbound/recovery.py trustbound/adversarial.py requirements-web.txt frontend/package-lock.json docs/day1-results.json; do
    git -C "$repo" cat-file -e "$commit:$required" || { echo 'Commit lacks current implementation' >&2; exit 1; }
done
while IFS= read -r path; do
    case "${path##*/}" in
        .env.example) ;;
        .env|.env.*) echo 'Commit includes a forbidden env file' >&2; exit 1 ;;
    esac
done < <(git -C "$repo" ls-tree -r --name-only "$commit")
release=/srv/trustbound/releases/$commit
[[ ! -e $release ]] || { echo 'Release exists; do not overwrite it' >&2; exit 1; }
mkdir -m 0755 -- "$release"
git -C "$repo" archive "$commit" | tar -x -C "$release"
unset VULTR_INFERENCE_API_KEY VULTR_MODEL TRUSTBOUND_ENABLE_LIVE TRUSTBOUND_ENABLE_RECOVERY_LIVE
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install -r "$release/requirements-web.txt"
(cd "$release/frontend" && npm ci --no-audit --no-fund && npm run build)
[[ ! -e $release/artifacts ]] || { echo 'Committed artifacts directory is not permitted' >&2; exit 1; }
ln -s /var/lib/trustbound/evidence "$release/artifacts"
printf '%s\n' "$commit" > "$release/RELEASE_COMMIT"
printf '%s\n' "Prepared $commit; not activated. Builds use committed sources only."
