#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x glab_venv/bin/guardrail-lab ]]; then
  echo "Missing glab_venv. Run: python3.11 -m venv glab_venv && glab_venv/bin/pip install -e ." >&2
  exit 1
fi

glab_venv/bin/guardrail-lab --config config.example.yaml all --archive \
  --notes "Scheduled regression run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
