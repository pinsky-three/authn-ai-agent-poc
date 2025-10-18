# Federation PoC - Testing Guide

## Quick Start

### 1. Start All Services

```bash
docker-compose up -d --build
```

### 2. Run Authentication Test

```bash
./test-auth.sh
```

## Services

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Mock Cognito | 9000 | http://localhost:9000 | Authentication & JWT generation |
| BFF | 8080 | http://localhost:8080 | Backend-for-Frontend |
| Agent | 8081 | http://localhost:8081 | LangGraph AI Agent |
| Acme API | 8082 | http://localhost:8082 | Protected API |
| Gateway | 8000 | http://localhost:8000 | Envoy proxy |
| OPA (Authz) | 8181 | http://localhost:8181 | Policy engine |
| Jaeger UI | 16686 | http://localhost:16686 | Distributed tracing |
| Redis | 6379 | localhost:6379 | Session storage |

## Mock Cognito Features

### Test Users

**Developer User:**
- Email: `testuser@example.com`
- Password: `TestPassword123!`
- Attributes:
  - team: `platform`
  - project: `poc`
  - env: `dev`
  - cost_center: `engineering`
  - groups: `developers`, `poc-team`

**Admin User:**
- Email: `admin@example.com`
- Password: `AdminPass456!`
- Attributes:
  - team: `platform`
  - project: `poc`
  - env: `prod`
  - cost_center: `engineering`
  - groups: `admins`, `developers`

### API Endpoints

#### 1. Health Check
```bash
curl http://localhost:9000/health
```

#### 2. Login (Get Tokens)
```bash
curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser@example.com",
    "password": "TestPassword123!"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGc...",
  "id_token": "eyJhbGc...",
  "refresh_token": "uuid",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

#### 3. AssumeRole (Federation)
```bash
# First, get ID token from login
ID_TOKEN="<from_login_response>"

curl -X POST http://localhost:9000/auth/assume-role \
  -H "Content-Type: application/json" \
  -d "{
    \"id_token\": \"$ID_TOKEN\",
    \"role_arn\": \"arn:aws:iam::000000000000:role/agent-ops-role\",
    \"session_name\": \"my-session\"
  }"
```

**Response:**
```json
{
  "Credentials": {
    "AccessKeyId": "ASIA...",
    "SecretAccessKey": "mock/...",
    "SessionToken": "eyJhbGc...",
    "Expiration": "2025-10-18T04:25:00Z"
  },
  "AssumedRoleUser": {
    "AssumedRoleId": "AROA...session-name",
    "Arn": "arn:aws:sts::000000000000:assumed-role/agent-ops-role/session-name"
  },
  "SessionTags": [
    {"Key": "team", "Value": "platform"},
    {"Key": "project", "Value": "poc"},
    {"Key": "env", "Value": "dev"},
    {"Key": "cost_center", "Value": "engineering"}
  ]
}
```

#### 4. Token Introspection
```bash
curl -X POST http://localhost:9000/auth/introspect \
  -H "Content-Type: application/json" \
  -d '{"token": "<access_token>"}'
```

#### 5. Token Revocation
```bash
curl -X POST http://localhost:9000/auth/revoke \
  -H "Content-Type: application/json" \
  -d '{"token": "<access_token>"}'
```

#### 6. List Users (Debug)
```bash
curl http://localhost:9000/users
```

#### 7. OIDC Discovery
```bash
curl http://localhost:9000/.well-known/openid-configuration
curl http://localhost:9000/.well-known/jwks.json
```

## Testing Scenarios

### Scenario 1: Authentication Flow
1. Login with test credentials
2. Receive JWT tokens with custom claims
3. Decode ID token to verify custom attributes (team, project, env, cost_center)
4. Use access token for API requests

### Scenario 2: AWS Federation (STS)
1. Login and obtain ID token
2. Call `/auth/assume-role` with ID token
3. Receive temporary AWS credentials
4. Session tags are populated from Cognito custom attributes
5. Use credentials for ABAC-enabled AWS operations

### Scenario 3: Token Revocation
1. Login and obtain access token
2. Use token for API request (should succeed)
3. Revoke token via `/auth/revoke`
4. Attempt to use token again (should fail)

### Scenario 4: Gateway + OPA Authorization
1. Login and get access token
2. Make request to gateway: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/acme/data`
3. Gateway forwards to OPA for policy decision
4. OPA evaluates based on JWT claims
5. Request proxied to backend if allowed

## Debugging

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mock_cognito
docker-compose logs -f authz
docker-compose logs -f gateway
```

### Check Service Health
```bash
docker-compose ps
```

### Stop Services
```bash
docker-compose down
```

### Rebuild After Changes
```bash
docker-compose up -d --build
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│        Mock Cognito (Port 9000)         │
│  - Login/Authentication                 │
│  - JWT Generation (ID + Access tokens)  │
│  - Custom claims (team, project, etc)   │
│  - STS AssumeRole simulation            │
└─────────────────────────────────────────┘
       │
       │ JWT with custom claims
       ▼
┌─────────────────────────────────────────┐
│           BFF (Port 8080)               │
│  - Session management                   │
│  - OIDC flow coordination               │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         Agent (Port 8081)               │
│  - LangGraph orchestration              │
│  - GitHub/AWS tool execution            │
│  - Uses federated credentials           │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│       Gateway (Envoy, Port 8000)        │
│  - JWT validation                       │
│  - OPA policy enforcement               │
└──────┬──────────────────────────────────┘
       │
       ├──────▶ OPA (Port 8181)
       │         Policy decisions
       │
       ▼
┌─────────────────────────────────────────┐
│       Acme API (Port 8082)              │
│  - Protected backend service            │
└─────────────────────────────────────────┘
```

## Token Structure

### ID Token Claims
```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "iss": "http://mock-cognito:9000",
  "aud": "api://acme-api",
  "token_use": "id",
  "email": "testuser@example.com",
  "email_verified": true,
  "custom:team": "platform",
  "custom:project": "poc",
  "custom:env": "dev",
  "custom:cost_center": "engineering",
  "cognito:groups": ["developers", "poc-team"]
}
```

### Access Token Claims
```json
{
  "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "iss": "http://mock-cognito:9000",
  "aud": "api://acme-api",
  "token_use": "access",
  "scope": "openid profile email",
  "username": "testuser@example.com"
}
```

## Next Steps

- [ ] Integrate mock Cognito with BFF OIDC flow
- [ ] Configure Envoy to validate JWTs from mock Cognito
- [ ] Update OPA policies to use custom claims for ABAC
- [ ] Implement GitHub App integration for code operations
- [ ] Add real AWS STS integration (optional, can use mock)
- [ ] Set up comprehensive OpenTelemetry tracing
- [ ] Create E2E test suite
