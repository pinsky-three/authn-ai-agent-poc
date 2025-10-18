#!/bin/bash
set -e

echo "===== Testing Complete PoC Setup ====="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Build and start services
echo "1. Building and starting all services..."
docker-compose up -d --build
echo ""

# Wait for services to be healthy
echo "2. Waiting for services to be healthy (30s)..."
sleep 30
echo ""

# Check service health
echo "3. Checking service health..."
services=("redis" "authz" "bff" "agent" "acme_api" "gateway" "jaeger" "mock_cognito")
for service in "${services[@]}"; do
    if docker-compose ps | grep -q "$service.*Up"; then
        echo "  ✓ $service is running"
    else
        echo "  ❌ $service is not running"
    fi
done
echo ""

# Test Mock Cognito
echo "4. Testing Mock Cognito authentication..."
echo "  → Authenticating as testuser@example.com..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser@example.com",
    "password": "TestPassword123!"
  }')

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo "  ✓ Authentication successful"
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    ID_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.id_token')
    echo "  ✓ Access token received: ${ACCESS_TOKEN:0:30}..."
    echo "  ✓ ID token received: ${ID_TOKEN:0:30}..."
else
    echo "  ❌ Authentication failed"
    echo "$LOGIN_RESPONSE" | jq '.'
    exit 1
fi
echo ""

# Decode and display ID token claims
echo "5. Verifying ID token claims (custom attributes)..."
CLAIMS=$(echo "$ID_TOKEN" | awk -F. '{print $2}' | base64 -d 2>/dev/null || echo "{}")
echo "$CLAIMS" | jq -r '
    "  → Subject (sub): \(.sub)",
    "  → Email: \(.email)",
    "  → Team: \(.["custom:team"])",
    "  → Project: \(.["custom:project"])",
    "  → Environment: \(.["custom:env"])",
    "  → Cost Center: \(.["custom:cost_center"])",
    "  → Groups: \(.["cognito:groups"] | join(", "))"
'
echo ""

# Test STS AssumeRole simulation
echo "6. Testing STS AssumeRole with Web Identity..."
ASSUME_ROLE_RESPONSE=$(curl -s -X POST http://localhost:9000/auth/assume-role \
  -H "Content-Type: application/json" \
  -d "{
    \"id_token\": \"$ID_TOKEN\",
    \"role_arn\": \"arn:aws:iam::000000000000:role/agent-ops-role\",
    \"session_name\": \"poc-test-session\"
  }")

if echo "$ASSUME_ROLE_RESPONSE" | jq -e '.Credentials' > /dev/null 2>&1; then
    echo "  ✓ AssumeRole successful"
    echo "$ASSUME_ROLE_RESPONSE" | jq -r '
        "  → Access Key: \(.Credentials.AccessKeyId)",
        "  → Assumed Role ARN: \(.AssumedRoleUser.Arn)",
        "  → Session Tags:"
    '
    echo "$ASSUME_ROLE_RESPONSE" | jq -r '.SessionTags[] | "    - \(.Key): \(.Value)"'
else
    echo "  ❌ AssumeRole failed"
    echo "$ASSUME_ROLE_RESPONSE" | jq '.'
fi
echo ""

# Test OPA endpoint
echo "7. Testing OPA authorization service..."
OPA_HEALTH=$(curl -s http://localhost:8181/health)
if [ "$OPA_HEALTH" == "{}" ]; then
    echo "  ✓ OPA is healthy"
else
    echo "  ⚠ OPA health check unexpected response: $OPA_HEALTH"
fi
echo ""

# Test Gateway with authentication
echo "8. Testing Gateway with JWT authentication..."
GATEWAY_RESPONSE=$(curl -s -X GET http://localhost:8000/acme/data \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -w "\nHTTP_STATUS:%{http_code}")

HTTP_STATUS=$(echo "$GATEWAY_RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
RESPONSE_BODY=$(echo "$GATEWAY_RESPONSE" | sed '/HTTP_STATUS/d')

if [ "$HTTP_STATUS" == "200" ]; then
    echo "  ✓ Gateway authenticated request successfully (HTTP 200)"
    echo "  Response: $RESPONSE_BODY"
else
    echo "  ⚠ Gateway response (HTTP $HTTP_STATUS)"
    echo "  Response: $RESPONSE_BODY"
fi
echo ""

# Test Jaeger
echo "9. Testing Jaeger tracing UI..."
JAEGER_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:16686)
if [ "$JAEGER_HEALTH" == "200" ]; then
    echo "  ✓ Jaeger UI is accessible at http://localhost:16686"
else
    echo "  ⚠ Jaeger UI returned HTTP $JAEGER_HEALTH"
fi
echo ""

echo "===== Test Summary ====="
echo ""
echo "Service Endpoints:"
echo "  • Mock Cognito:  http://localhost:9000"
echo "  • BFF:           http://localhost:8080"
echo "  • Agent:         http://localhost:8081"
echo "  • Acme API:      http://localhost:8082"
echo "  • Gateway:       http://localhost:8000"
echo "  • OPA:           http://localhost:8181"
echo "  • Jaeger UI:     http://localhost:16686"
echo ""
echo "Test Credentials:"
echo "  Developer: testuser@example.com / TestPassword123!"
echo "  Admin:     admin@example.com / AdminPass456!"
echo ""
echo "Next Steps:"
echo "  1. View logs: docker-compose logs -f [service_name]"
echo "  2. Test authentication: curl -X POST http://localhost:9000/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"testuser@example.com\",\"password\":\"TestPassword123!\"}'"
echo "  3. View traces: Open http://localhost:16686 in your browser"
echo "  4. Stop services: docker-compose down"
echo ""
echo "✓ Setup complete!"
