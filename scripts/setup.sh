#!/usr/bin/env bash
# First-time local dev setup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 InvestorInsights — First-time setup"

# Copy .env if not exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo "✅ Created .env from .env.example — edit it with your config"
else
    echo "ℹ️  .env already exists, skipping"
fi

# Build and start services
echo "🔨 Building Docker images..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" build

echo "📦 Starting services..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" up -d

echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

echo "🗄️  Running database migrations..."
docker compose -f "$PROJECT_ROOT/docker-compose.dev.yml" run --rm api alembic upgrade head

echo "✅ Setup complete! Run 'make up' to start services."
