#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
  echo "Usage: RENDER_DEPLOY_HOOK_URL=... $0 <git-sha>" >&2
  exit 2
fi

if [[ -z "${RENDER_DEPLOY_HOOK_URL:-}" ]]; then
  echo "RENDER_DEPLOY_HOOK_URL is required." >&2
  exit 2
fi

curl --fail --silent --show-error --output /dev/null --max-time 30 \
  --get --data-urlencode "ref=$1" "$RENDER_DEPLOY_HOOK_URL"
echo "Render accepted the deploy request for the requested commit."
