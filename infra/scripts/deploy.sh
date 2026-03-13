#!/usr/bin/env bash
# ============================================================
# Deploy Azure infrastructure for InvestorInsights
# Usage: ./infra/scripts/deploy.sh [dev|staging|prod]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-dev}"
LOCATION="eastus2"

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

echo "🚀 Deploying InvestorInsights infrastructure — environment: $ENVIRONMENT"
echo "   Region: $LOCATION"
echo "   Template: $INFRA_DIR/main.bicep"
echo "   Parameters: $INFRA_DIR/parameters/$ENVIRONMENT.bicepparam"
echo ""

# Verify Azure CLI is logged in
if ! az account show &>/dev/null; then
    echo "❌ Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
echo "   Subscription: $SUBSCRIPTION"
echo ""
read -rp "Proceed with deployment? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "📦 Starting deployment..."

az deployment sub create \
    --location "$LOCATION" \
    --template-file "$INFRA_DIR/main.bicep" \
    --parameters "$INFRA_DIR/parameters/$ENVIRONMENT.bicepparam" \
    --name "investorinsights-$ENVIRONMENT-$(date +%Y%m%d-%H%M%S)" \
    --verbose

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Run seed-keyvault.sh to populate initial secrets"
echo "  2. Build and push Docker images to ACR"
echo "  3. Update Container Apps with new images"
