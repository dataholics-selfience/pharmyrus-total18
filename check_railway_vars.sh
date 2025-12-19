#!/bin/bash
# Check Railway Environment Variables

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         🔍 RAILWAY ENVIRONMENT CHECK                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking Railway variables..."
echo ""

# Check if railway CLI is available
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI not installed${NC}"
    echo "Install: npm i -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${RED}❌ Not logged into Railway${NC}"
    echo "Run: railway login"
    exit 1
fi

echo -e "${GREEN}✅ Railway CLI ready${NC}"
echo ""

# Get all variables
echo "Current variables:"
railway variables | grep -E "(EPO_|USE_FIRESTORE|GROK_|PORT)" || echo "No variables set"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}Required variables:${NC}"
echo ""
echo "railway variables set EPO_CONSUMER_KEY='G5wJypxeg0GXEJoMGP37tdK370aKxeMszGKAkD6QaR0yiR5X'"
echo "railway variables set EPO_CONSUMER_SECRET='zg5AJ0EDzXdJey3GaFNM8ztMVxHKXRrAihXH93iS5ZAzKPAP'"
echo "railway variables set USE_FIRESTORE='false'"
echo ""
echo -e "${YELLOW}Recommended:${NC}"
echo ""
echo "railway variables set GROK_API_KEY='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'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
