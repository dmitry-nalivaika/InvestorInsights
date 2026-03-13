#!/usr/bin/env bash
# ⚠️  Wipe ALL local data (development only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "⚠️  This will DESTROY all local data (databases, volumes, vectors)."
read -rp "Are you sure? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

echo "🗑️  Tearing down services and volumes..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" down -v

echo "📦 Starting fresh services..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" up -d

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

echo "🗄️  Running database migrations..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" run --rm api alembic upgrade head

echo "🌱 Seeding defaults..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" run --rm api \
    python -m app.scripts.seed_defaults

echo "✅ Reset complete."
