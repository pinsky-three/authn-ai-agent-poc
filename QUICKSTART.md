# Quick Start Guide

## 5-Minute Setup

### 1. Prerequisites
- Docker and Docker Compose installed
- Okta Dev account (free at https://developer.okta.com)

### 2. Configure Okta (5 minutes)

Create in your Okta Admin Console:

**Authorization Server** (`/oauth2/poc`):
- Audience: `api://acme-api`
- Scopes: `acme.read`, `acme.write`
- Claims: `email` (user.email), `roles` (from groups)

**OIDC App** (Web Application):
- Grant types: Authorization Code + Refresh Token
- PKCE: Required
- Redirect URI: `http://localhost:8080/auth/callback`

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```bash
OKTA_ISSUER=https://YOUR_DOMAIN.okta.com/oauth2/poc
OKTA_CLIENT_ID=your_client_id
OKTA_CLIENT_SECRET=your_client_secret
OIDC_REDIRECT_URI=http://localhost:8080/auth/callback
ACME_AUDIENCE=api://acme-api
ACME_SCOPES=acme.read
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
SESSION_COOKIE_NAME=poc_session
ENVOY_JWKS_URI=https://YOUR_DOMAIN.okta.com/oauth2/poc/v1/keys
OKTA_ISSUER_HOST=YOUR_DOMAIN.okta.com
OPA_URL=http://authz:8181/v1/data/policy/allow
```

### 4. Start Services

```bash
make up
```

### 5. Test

```bash
# Health check
./test.sh

# Authenticate
open http://localhost:8080/auth/login
```

## Architecture at a Glance

```
Browser
   │
   │ (1) Auth Code + PKCE
   ↓
  BFF ← → Okta (OIDC)
   │
   │ (2) Bearer token
   ↓
Agent (LangGraph)
   │
   │ (3) Bearer token
   ↓
Gateway (Envoy) → OPA (policy)
   │
   │ (4) JWT validated
   ↓
ACME API
```

## Token Flow

1. **User authenticates** → BFF stores tokens in Redis, returns httpOnly cookie
2. **User calls `/run-agent`** → BFF forwards ACME-scoped token to Agent
3. **Agent tool executes** → Calls Gateway with bearer token (token never in LLM context)
4. **Gateway validates** → Envoy checks JWT signature, queries OPA for authz
5. **OPA decides** → Allow/deny based on policy (scopes, roles, path)
6. **ACME responds** → Returns data to Agent → BFF → User

## Key Security Features

✅ PKCE prevents authorization code interception
✅ Server-side sessions (tokens never in browser)
✅ Audience-scoped tokens (per-API)
✅ Multi-layer JWT validation (Envoy + ACME API)
✅ Policy-based authorization (OPA Rego)
✅ Tokens isolated from LLM prompts

## Common Commands

```bash
# Start all services
make up

# View logs
make logs

# Stop services
make down

# Full rebuild
make reset

# Run tests
./test.sh
```

## Testing the Full Flow

1. **Authenticate**:
   ```bash
   open http://localhost:8080/auth/login
   ```

2. **Get your profile**:
   ```bash
   open http://localhost:8080/me
   ```

3. **Run agent** (with session cookie from browser):
   ```bash
   curl -X POST http://localhost:8080/run-agent \
     -H "Content-Type: application/json" \
     -d '{"task": "whoami"}' \
     --cookie "poc_session=YOUR_COOKIE"
   ```

4. **Expected response**:
   ```json
   {
     "user": "00u...",
     "result": {
       "task": "whoami",
       "profile": {
         "sub": "00u...",
         "email": "user@example.com",
         "roles": []
       }
     }
   }
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid token" | Check `OKTA_ISSUER` and `ACME_AUDIENCE` match exactly |
| Gateway 401 | Verify `OKTA_ISSUER_HOST` is hostname only (no https://) |
| OPA denies | Check `docker compose logs authz` and policy.rego |
| Session not found | Redis restarted; re-authenticate at `/auth/login` |
| Service 503 | Check `docker compose ps` - ensure all services are up |

## Next Steps

See `SETUP.md` for detailed configuration and `README.md` for architecture deep-dive.

For production hardening:
- Enable HTTPS everywhere
- Implement token rotation
- Add resource indicators (RFC 8707)
- Deploy OpenTelemetry for tracing
- Add mTLS between services
- Enhance OPA policies with fine-grained RBAC
