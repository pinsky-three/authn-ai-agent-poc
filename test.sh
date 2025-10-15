#!/bin/bash
set -e

echo "=== LangGraph AuthN/AuthZ PoC Test Suite ==="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health checks
echo "1. Testing service health..."
echo -n "   BFF: "
if curl -s http://localhost:8080/ | grep -q "ok"; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "   Agent: "
if curl -s http://localhost:8081/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "   ACME API: "
if curl -s http://localhost:8082/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "   Gateway: "
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo -n "   OPA: "
if curl -s http://localhost:8181/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

echo

# Test 2: Unauthenticated requests should fail
echo "2. Testing security (unauthenticated requests)..."
echo -n "   BFF /me without cookie: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/me)
if [ "$STATUS" = "401" ]; then
    echo -e "${GREEN}✓ (401)${NC}"
else
    echo -e "${RED}✗ (got $STATUS)${NC}"
fi

echo -n "   ACME API without token: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/acme/v1/whoami)
if [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
    echo -e "${GREEN}✓ ($STATUS)${NC}"
else
    echo -e "${RED}✗ (got $STATUS)${NC}"
fi

echo

# Test 3: Manual login flow
echo "3. Authentication flow:"
echo -e "   ${YELLOW}Action required:${NC} Please authenticate manually"
echo "   1. Open: http://localhost:8080/auth/login"
echo "   2. Complete Okta login"
echo "   3. After redirect, copy the session cookie"
echo

read -p "   Press Enter when authenticated..."

# Test 4: Check if user has session
echo
echo "4. Testing authenticated endpoints..."
echo "   Open your browser and check:"
echo "   - http://localhost:8080/me (should show your profile)"
echo

# Instructions for testing agent
echo "5. Testing agent execution:"
echo "   To test the agent, use curl with your session cookie:"
echo
echo -e "   ${YELLOW}curl -X POST http://localhost:8080/run-agent \\\\${NC}"
echo -e "   ${YELLOW}  -H 'Content-Type: application/json' \\\\${NC}"
echo -e "   ${YELLOW}  -d '{\"task\": \"whoami\"}' \\\\${NC}"
echo -e "   ${YELLOW}  --cookie 'poc_session=YOUR_SESSION_COOKIE'${NC}"
echo

echo "=== Test suite complete ==="
echo
echo "For full E2E testing:"
echo "1. Authenticate at http://localhost:8080/auth/login"
echo "2. Get your session cookie from browser dev tools"
echo "3. Call /run-agent endpoint with the cookie"
echo "4. Verify the agent successfully calls ACME API through gateway"
