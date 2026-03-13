#!/usr/bin/env bash
# Seed default analysis profile
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🌱 Seeding default analysis profile..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" run --rm api \
    python -m app.scripts.seed_defaults

echo "✅ Seed complete."
