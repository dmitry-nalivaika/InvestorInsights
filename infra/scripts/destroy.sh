#!/usr/bin/env bash
# ============================================================
# Destroy Azure infrastructure for InvestorInsights
# ⚠️  This will DELETE the entire resource group and ALL data!
# Usage: ./infra/scripts/destroy.sh [dev|staging|prod]
# ============================================================
set -euo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="investorinsights"
RESOURCE_GROUP="rg-${PROJECT_NAME}-${ENVIRONMENT}"

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "❌ Invalid environment: $ENVIRONMENT. Must be dev, staging, or prod."
    exit 1
fi

if [[ "$ENVIRONMENT" == "prod" ]]; then
    echo "⚠️  WARNING: You are about to destroy the PRODUCTION environment!"
    echo "   This action is IRREVERSIBLE and will delete ALL data."
    echo ""
    read -rp "Type 'DELETE PRODUCTION' to confirm: " confirm
    if [[ "$confirm" != "DELETE PRODUCTION" ]]; then
        echo "Aborted."
        exit 0
    fi
else
    echo "⚠️  This will DESTROY resource group: $RESOURCE_GROUP"
    echo "   All resources and data within it will be permanently deleted."
    echo ""
    read -rp "Are you sure? (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Verify Azure CLI is logged in
if ! az account show &>/dev/null; then
    echo "❌ Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi

echo ""
echo "🗑️  Deleting resource group: $RESOURCE_GROUP ..."

az group delete \
    --name "$RESOURCE_GROUP" \
    --yes \
    --no-wait

echo ""
echo "✅ Resource group deletion initiated (async)."
echo "   Use 'az group show --name $RESOURCE_GROUP' to check status."
