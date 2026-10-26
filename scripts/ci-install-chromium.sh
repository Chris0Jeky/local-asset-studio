#!/usr/bin/env bash
# Bounded CI setup for the explicitly pinned Ubuntu 24.04 browser jobs.
set -euo pipefail

source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 ]]; then
  printf '%s\n' 'Chromium CI dependency setup requires Ubuntu 24.04.' >&2
  exit 2
fi
if [[ ! -r /usr/share/keyrings/ubuntu-archive-keyring.gpg ]]; then
  printf '%s\n' 'The Ubuntu archive signing keyring is unavailable.' >&2
  exit 2
fi

ci_python="$(command -v python)"
ci_apt_dir="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/studio-browser-apt.XXXXXX")"
trap 'rm -rf -- "$ci_apt_dir"' EXIT
# APT configuration quotes paths; runner paths with spaces are supported.
case "$ci_apt_dir" in
  *\"*|*\\*|*$'\n'*|*$'\r'*) printf '%s\n' 'Unsupported character in the runner temporary path.' >&2; exit 2 ;;
esac

cat > "$ci_apt_dir/ubuntu.sources" <<'SOURCES'
Types: deb
URIs: https://archive.ubuntu.com/ubuntu
Suites: noble noble-updates
Components: main universe
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: https://security.ubuntu.com/ubuntu
Suites: noble-security
Components: main universe
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
SOURCES

cat > "$ci_apt_dir/apt.conf" <<CONFIG
# APT_CONFIG loads before system snippets; prevent later runner overrides.
Dir::Etc::parts "-";
Dir::Etc::main "-";
Dir::Etc::sourcelist "$ci_apt_dir/ubuntu.sources";
Dir::Etc::sourceparts "-";
Acquire::Retries "1";
Acquire::http::Timeout "15";
Acquire::https::Timeout "15";
APT::Update::Error-Mode "any";
CONFIG

# Running install-deps as root avoids Playwright's internal sudo dropping
# APT_CONFIG. env sets it after sudo resets its environment. timeout also runs
# as root so it can terminate the complete dependency process group on expiry.
sudo -n env APT_CONFIG="$ci_apt_dir/apt.conf" \
  timeout --kill-after=10s 150s "$ci_python" -m playwright install-deps chromium

# Browser files belong to the ordinary runner user and its Playwright cache.
timeout --kill-after=10s 60s "$ci_python" -m playwright install chromium
