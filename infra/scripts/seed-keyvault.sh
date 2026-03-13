#!/usr/bin/env bash
# ============================================================
# Seed Azure Key Vault with initial secrets
# Run AFTER deploy.sh and BEFORE first application start.
# Usage: ./infra/scripts/seed-keyvault.sh [dev|staging|prod]
# ============================================================
set -euo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="investorinsights"
# Key Vault name is truncated to 24 chars in Bicep: kv-${projectName}-${env}
KV_NAME="kv-${PROJECT_NAME}-${ENVIRONMENT}"
# Truncate to 24 chars to match Bicep logic
KV_NAME="${KV_NAME:0:24}"

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

# Verify Azure CLI is logged in
if ! az account show &>/dev/null; then
    echo "❌ Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi

echo "🔐 Seeding Key Vault: $KV_NAME"
echo ""

# ── Helper function ──────────────────────────────────────────────
set_secret() {
    local name="$1"
    local value="$2"
    local description="${3:-}"

    if [[ -z "$value" ]]; then
        echo "⚠️  Skipping $name (empty value)"
        return
    fi

    echo "   Setting: $name"
    az keyvault secret set \
        --vault-name "$KV_NAME" \
        --name "$name" \
        --value "$value" \
        --description "$description" \
        --output none 2>/dev/null
}

# ── Prompt for secrets ───────────────────────────────────────────
echo "Enter secrets (press Enter to skip optional ones):"
echo ""

read -rp "  API Auth Key (V1 authentication): " API_AUTH_KEY
read -rp "  SEC EDGAR User-Agent (e.g., YourApp/1.0 (email@example.com)): " SEC_EDGAR_UA

echo ""
echo "📝 Setting secrets..."

# API auth key
set_secret "api-auth-key" "$API_AUTH_KEY" "V1 API authentication key"

# SEC EDGAR User-Agent
if [[ -n "$SEC_EDGAR_UA" ]]; then
    set_secret "sec-edgar-user-agent" "$SEC_EDGAR_UA" "SEC EDGAR API User-Agent header"
fi

echo ""
echo "✅ Key Vault seeded successfully."
echo ""
echo "Note: Database, Blob Storage, OpenAI, and Redis connection secrets"
echo "are automatically set by the Bicep deployment (deploy.sh)."
echo ""
echo "To verify secrets:"
echo "  az keyvault secret list --vault-name $KV_NAME --output table"
