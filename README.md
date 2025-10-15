# LangGraph AuthN/AuthZ PoC

Production-shaped proof of concept demonstrating end-to-end AuthN/AuthZ for LangGraph agents in a microservices layout.

## Architecture

- **BFF**: OIDC client (Okta Auth Code + PKCE), session management (Redis), user-facing API
- **Agent**: LangGraph service with tool adapters (tokens never exposed to LLM)
- **ACME API**: Resource server requiring `aud=api://acme-api` tokens
- **Gateway**: Envoy proxy with JWT verification and OPA policy enforcement
- **AuthZ**: OPA policy server for fine-grained authorization decisions

## Prerequisites

1. **Okta Dev Account** - Set up:
   - Custom Authorization Server at `https://{oktaDomain}/oauth2/poc`
   - Audience: `api://acme-api`
   - Scopes: `acme.read`, `acme.write`
   - Claims in access token: `sub`, `email`, `roles`
   - OIDC Web App with:
     - Grant types: Authorization Code, Refresh Token
     - PKCE required
     - Redirect URI: `http://localhost:8080/auth/callback`
     - Post-logout URI: `http://localhost:8080/`

2. **Docker & Docker Compose**

## Quick Start

1. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Okta values
   ```

2. **Start all services**:
   ```bash
   make up
   ```

3. **Test authentication flow**:
   - Open http://localhost:8080/auth/login
   - Authenticate with Okta
   - Redirected to `/me` showing your profile

4. **Test agent execution**:
   ```bash
   curl -X POST http://localhost:8080/run-agent \
     -H "Content-Type: application/json" \
     -d '{"task": "whoami"}' \
     --cookie "poc_session=<cookie_from_browser>"
   ```

## Service Endpoints

- **BFF**: http://localhost:8080
  - `/auth/login` - Initiate OIDC flow
  - `/auth/callback` - OIDC callback
  - `/me` - User profile
  - `/run-agent` - Execute agent task
- **Agent**: http://localhost:8081 (internal)
- **ACME API**: http://localhost:8082 (internal, behind gateway)
- **Gateway**: http://localhost:8000
- **OPA**: http://localhost:8181

## Token Flow

1. User authenticates → Okta issues access token with `aud=api://acme-api`
2. BFF stores tokens server-side, issues httpOnly session cookie
3. User calls `/run-agent` → BFF forwards scoped token to Agent
4. Agent tool calls Gateway with bearer token
5. Envoy validates JWT (JWKS), queries OPA for authz decision
6. OPA allows based on policy (scope/role checks)
7. Request proxied to ACME API
8. ACME API validates token and returns data

## Security Features

- ✅ OIDC Auth Code flow with PKCE
- ✅ Server-side session management (no tokens in browser)
- ✅ Audience-scoped access tokens
- ✅ JWT signature verification at multiple layers
- ✅ Gateway-level policy enforcement (Envoy + OPA)
- ✅ Tokens never exposed to LLM/agent prompts
- ✅ Short-lived sessions with Redis backing

## Development

```bash
# View logs
make logs

# Stop services
make down

# Rebuild and restart
make reset
```

## Next Steps

- [ ] Add refresh token rotation
- [ ] Implement resource indicators for per-service tokens
- [ ] Add DPoP for token binding
- [ ] Forward verified claims to OPA for fine-grained RBAC
- [ ] Add OpenTelemetry tracing
- [ ] Implement token exchange (RFC 8693) for OBO flows
- [ ] Add step-up MFA for sensitive operations
- [ ] Add mTLS between services

## Troubleshooting

**"Invalid token" errors**: Check that `OKTA_ISSUER` and `ACME_AUDIENCE` match your Okta config exactly.

**Gateway returns 401**: Verify JWKS URI is accessible and `OKTA_ISSUER_HOST` is correct (without https://).

**OPA denies request**: Check `authz/policy.rego` - the PoC policy is minimal. Add scope/role checks as needed.

**Session not found**: Redis may have restarted. Re-authenticate at `/auth/login`.
