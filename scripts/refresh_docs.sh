#!/usr/bin/env bash
# Re-fetch the full TypeSafe/Jev docs dump locally (gitignored; the typesafe-docs MCP is the primary source).
set -euo pipefail
cd "$(dirname "$0")/.."
curl -sL https://docs.typesafe.ai/llms.txt -o docs/jev/llms.txt
curl -sL https://docs.typesafe.ai/llms-full.txt -o docs/jev/llms-full.txt
echo "docs/jev refreshed ($(wc -c < docs/jev/llms-full.txt) bytes)"
