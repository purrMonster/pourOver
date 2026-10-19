#!/usr/bin/env bash
# Runs tests/contract against a throwaway copy of the pinned Vikunja.
# Downloads the release binary once, checks its sha256, starts it on
# 127.0.0.1 with SQLite in a temp dir and registration on, runs pytest, stops it.
# Bump VIKUNJA_VERSION and VIKUNJA_SHA256 together with the purrBrews stack.
set -euo pipefail

VIKUNJA_VERSION="2.7.0"
VIKUNJA_SHA256="$(cat "$(dirname "$0")/vikunja.sha256")"
PORT="${VIKUNJA_CONTRACT_PORT:-34560}"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/pourover-contract"
BIN="$CACHE/vikunja-v${VIKUNJA_VERSION}-linux-amd64"

mkdir -p "$CACHE"
if [[ ! -x "$BIN" ]]; then
  zip="$CACHE/vikunja-${VIKUNJA_VERSION}.zip"
  curl -fsSL -o "$zip" "https://github.com/go-vikunja/vikunja/releases/download/v${VIKUNJA_VERSION}/vikunja-v${VIKUNJA_VERSION}-linux-amd64-full.zip"
  unzip -o -q "$zip" "vikunja-v${VIKUNJA_VERSION}-linux-amd64" -d "$CACHE"
  rm -f "$zip"
fi
echo "${VIKUNJA_SHA256}  ${BIN}" | sha256sum -c --quiet -

work="$(mktemp -d)"
trap 'kill "$pid" 2>/dev/null || true; rm -rf "$work"' EXIT
(
  cd "$work"
  VIKUNJA_SERVICE_INTERFACE="127.0.0.1:${PORT}" \
  VIKUNJA_SERVICE_PUBLICURL="http://127.0.0.1:${PORT}/" \
  VIKUNJA_SERVICE_ENABLEREGISTRATION=true \
  VIKUNJA_SERVICE_TIMEZONE=Asia/Kolkata \
  VIKUNJA_DATABASE_TYPE=sqlite \
  VIKUNJA_DATABASE_PATH="$work/vikunja.db" \
  VIKUNJA_FILES_BASEPATH="$work/files" \
  VIKUNJA_MAILER_ENABLED=false \
  exec "$BIN" web
) > "$work/vikunja.log" 2>&1 &
pid=$!

for _ in $(seq 1 40); do
  curl -fsS "http://127.0.0.1:${PORT}/api/v2/info" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fsS "http://127.0.0.1:${PORT}/api/v2/info" | python3 -c 'import json,sys; print("Vikunja", json.load(sys.stdin)["version"])'

VIKUNJA_CONTRACT_URL="http://127.0.0.1:${PORT}" python3 -m pytest -q tests/contract "$@"
