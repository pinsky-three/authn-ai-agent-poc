#!/bin/bash
set -e

echo "Testing Mock Cognito Authentication"
echo ""

# Test 1: Health check
echo "1. Health check..."
curl -s http://localhost:9000/health | jq '.'
echo ""

# Test 2: Login
echo "2. Login as testuser@example.com..."
RESPONSE=$(cat <<EOF | curl -s -X POST http://localhost:9000/auth/login -H "Content-Type: application/json" -d @-
{
  "username": "testuser@example.com",
  "password": "TestPassword123!"
}
EOF
)

echo "$RESPONSE" | jq '.'
echo ""

# Extract tokens
ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
ID_TOKEN=$(echo "$RESPONSE" | jq -r '.id_token')

if [ "$ACCESS_TOKEN" != "null" ]; then
    echo "✓ Access token received"
    echo ""

    # Decode ID token
    echo "3. ID Token Claims:"
    echo "$ID_TOKEN" | awk -F. '{print $2}' | base64 -d 2>/dev/null | jq '.'
    echo ""

    # Test AssumeRole
    echo "4. Testing STS AssumeRole..."
    cat <<EOF | curl -s -X POST http://localhost:9000/auth/assume-role -H "Content-Type: application/json" -d @- | jq '.'
{
  "id_token": "$ID_TOKEN",
  "role_arn": "arn:aws:iam::000000000000:role/agent-ops-role",
  "session_name": "test-session"
}
EOF
else
    echo "❌ Authentication failed"
fi
