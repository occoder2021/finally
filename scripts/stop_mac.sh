#!/usr/bin/env bash
# Stop and remove the FinAlly container (macOS/Linux).
#
# Does NOT remove the `finally-data` volume — the portfolio and chat history
# persist across stop/start cycles. Idempotent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

docker compose down

echo "FinAlly stopped. Data volume 'finally-data' preserved — run scripts/start_mac.sh to resume."
