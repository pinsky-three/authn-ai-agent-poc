# Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           Browser/Client                        │
└───────────────────┬─────────────────────────────────────────────┘
                    │
                    │ HTTPS (httpOnly session cookie)
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                    BFF (Backend for Frontend)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ • OIDC Client (Auth Code + PKCE flow)                   │  │
│  │ • Session Management (Redis-backed)                     │  │
│  │ • Token Storage (server-side only)                      │  │
│  │ • User-facing API endpoints                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                   Port: 8080                                    │
└───┬────────────────────────────────┬────────────────────────────┘
    │                                │
    │ OAuth2/OIDC                    │ Bearer token (aud=api://acme-api)
    │                                │
    ▼                                ▼
┌──────────────────┐     ┌──────────────────────────────────────┐
│  Okta (IdP)      │     │        Agent Service                 │
│  ┌────────────┐  │     │  ┌───────────────────────────────┐  │
│  │ Auth Server│  │     │  │ LangGraph State Machine       │  │
│  │ /oauth2/poc│  │     │  │ • Orchestrates tools          │  │
│  └────────────┘  │     │  │ • Token never in LLM context  │  │
│  • Issues tokens │     │  │ • Secure tool execution       │  │
│  • JWKS endpoint │     │  └───────────────────────────────┘  │
│  • User AuthN    │     │           Port: 8081                 │
└──────────────────┘     └────┬─────────────────────────────────┘
                              │
                              │ Bearer token
                              │
                              ▼
            ┌─────────────────────────────────────┐
            │        Envoy Gateway                │
            │  ┌──────────────────────────────┐   │
            │  │ JWT Authentication Filter    │   │
            │  │ • Validates JWT signature    │   │
            │  │ • Checks iss, aud, exp       │   │
            │  │ • Fetches JWKS from Okta     │   │
            │  └──────────────────────────────┘   │
            │  ┌──────────────────────────────┐   │
            │  │ External Authorization       │◄──┼──┐
            │  │ • Calls OPA for policy check │   │  │
            │  │ • Passes request context     │   │  │
            │  └──────────────────────────────┘   │  │
            │           Port: 8000                 │  │
            └─────┬───────────────────────────────┘  │
                  │                                   │
                  │ Authorized request                │
                  │                                   │
                  ▼                                   │
    ┌────────────────────────────────┐               │
    │       ACME API                 │               │
    │  ┌──────────────────────────┐  │         ┌────▼─────┐
    │  │ Resource Server          │  │         │   OPA    │
    │  │ • JWT verification       │  │         │  ┌─────┐ │
    │  │ • Business logic         │  │         │  │Rego │ │
    │  │ • Protected resources    │  │         │  │Rules│ │
    │  └──────────────────────────┘  │         │  └─────┘ │
    │       Port: 8082                │         │  8181   │
    └─────────────────────────────────┘         └─────────┘

    ┌─────────────────────────────────┐
    │        Redis                    │
    │  • Session storage              │
    │  • Token cache                  │
    │  • TTL: 8 hours                 │
    │       Port: 6379                │
    └─────────────────────────────────┘
```

## Request Flow

### Authentication Flow (OIDC)

```
1. User → BFF: GET /auth/login
2. BFF → Okta: Redirect with Auth Code request + PKCE challenge
3. User ← Okta: Login form
4. User → Okta: Credentials
5. Okta → BFF: Redirect to /auth/callback?code=...
6. BFF → Okta: POST /token (code, verifier)
7. BFF ← Okta: {access_token, id_token, refresh_token}
8. BFF → Redis: Store session data with tokens
9. BFF → User: Set-Cookie (httpOnly, secure)
10. BFF → User: Redirect to /me
```

### Agent Execution Flow

```
1. User → BFF: POST /run-agent + session cookie
2. BFF → Redis: Lookup session → get access_token
3. BFF → Agent: POST /run + Bearer token + X-User-Sub
4. Agent: Execute LangGraph state machine
5. Agent Tool → Gateway: GET /acme/v1/whoami + Bearer token
6. Gateway (Envoy):
   a. JWT Authentication Filter:
      - Extract JWT from Authorization header
      - Fetch JWKS from Okta (cached)
      - Verify signature, iss, aud, exp
   b. External Authorization Filter:
      - Call OPA: POST /v1/data/policy/allow
      - Pass request context (method, path, headers)
7. OPA: Evaluate policy.rego rules
   - Check path matches /acme/*
   - Check method is GET
   - Check bearer token present
   → Return: {"result": true}
8. Gateway → ACME API: Proxied request with Bearer token
9. ACME API:
   - Verify JWT (signature, iss, aud, exp)
   - Extract claims (sub, email, roles)
   - Return user profile
10. ACME API → Gateway → Agent → BFF → User: Response
```

## Security Layers

### Layer 1: Transport Security
- HTTPS everywhere (production)
- TLS 1.3 minimum
- Certificate pinning (optional)

### Layer 2: Authentication
- **Browser → BFF**: Session cookie (httpOnly, secure, sameSite)
- **BFF → Okta**: OAuth2 Auth Code + PKCE
- **BFF → Agent**: Bearer token (short-lived, audience-scoped)
- **Agent → Gateway**: Same bearer token
- **Gateway → ACME**: Proxied bearer token

### Layer 3: Token Validation
- **Envoy Gateway**:
  - JWT signature verification (JWKS)
  - Issuer validation (iss claim)
  - Audience validation (aud claim)
  - Expiration check (exp claim)
- **ACME API**:
  - Redundant JWT verification
  - Claim extraction and validation

### Layer 4: Authorization
- **OPA Policy Engine**:
  - Path-based access control
  - Method-based access control
  - Scope/role-based access control (extensible)
  - Custom business logic in Rego

### Layer 5: Isolation
- **Agent Design**:
  - Tokens stored in state, not passed to LLM
  - Tools receive tokens via runtime injection
  - No secrets in prompts or logs

## Component Responsibilities

### BFF (Port 8080)
**Purpose**: User-facing API, OIDC client, session management

**Responsibilities**:
- Implement OAuth2 Auth Code + PKCE flow
- Store tokens server-side (Redis)
- Issue httpOnly session cookies
- Validate sessions on incoming requests
- Forward authenticated requests to backend services

**Security Controls**:
- CSRF protection (sameSite cookies)
- Session TTL enforcement
- Token refresh (if supported)
- No token exposure to client

### Agent (Port 8081)
**Purpose**: LangGraph state machine, tool orchestration

**Responsibilities**:
- Execute agent workflows
- Coordinate tool calls
- Maintain user context (sub, token)
- Never expose tokens to LLM

**Security Controls**:
- Require bearer token + user sub on all requests
- Pass tokens to tools via runtime config (not prompts)
- Validate tool permissions based on user context
- Log all tool executions with user attribution

### ACME API (Port 8082)
**Purpose**: Resource server, business logic

**Responsibilities**:
- Validate incoming JWTs
- Enforce audience requirement (aud=api://acme-api)
- Implement business logic
- Return protected resources

**Security Controls**:
- JWT verification (signature, claims)
- Audience enforcement
- Scope/role-based endpoint access
- Rate limiting (recommended)
- Audit logging

### Gateway (Port 8000)
**Purpose**: Ingress proxy, centralized authN/authZ

**Responsibilities**:
- Terminate TLS (production)
- Validate JWTs via JWKS
- Query OPA for authorization decisions
- Route requests to backend services
- Add security headers

**Security Controls**:
- JWT authentication filter
- External authorization (OPA)
- Rate limiting (recommended)
- Request/response transformation
- Header sanitization

### OPA (Port 8181)
**Purpose**: Policy decision point

**Responsibilities**:
- Evaluate Rego policies
- Return allow/deny decisions
- Support dynamic policy updates
- Log all decisions

**Security Controls**:
- Immutable policy evaluation
- No direct access to secrets
- Audit all decisions
- Policy versioning (recommended)

### Redis (Port 6379)
**Purpose**: Session storage, caching

**Responsibilities**:
- Store session data with TTL
- Cache JWKS (optional)
- Provide fast lookups

**Security Controls**:
- Network isolation (Docker network)
- AUTH password (production)
- Encryption at rest (production)
- Regular backups (production)

## Token Claims

### Access Token (from Okta)
```json
{
  "iss": "https://YOUR_DOMAIN.okta.com/oauth2/poc",
  "aud": "api://acme-api",
  "sub": "00u...",
  "email": "user@example.com",
  "roles": ["user", "admin"],
  "scope": "openid profile email acme.read",
  "exp": 1234567890,
  "iat": 1234567800
}
```

### Session Data (in Redis)
```json
{
  "sub": "00u...",
  "email": "user@example.com",
  "roles": ["user", "admin"],
  "access_token": "eyJ...",
  "refresh_token": "abc..."
}
```

## Network Topology (Docker)

```
Docker Network: authn-ai-agent-poc_default

┌─────────────┐
│   redis     │ :6379
└─────────────┘

┌─────────────┐
│    bff      │ :8080 → exposed
└─────┬───────┘
      │ → redis
      │ → agent

┌─────▼───────┐
│   agent     │ :8081 → exposed (dev)
└─────┬───────┘
      │ → gateway

┌─────▼───────┐
│   gateway   │ :8000 → exposed
└─────┬───┬───┘
      │   └────→ opa :8181
      │
      ▼
┌─────────────┐
│  acme_api   │ :8082 → NOT exposed (behind gateway)
└─────────────┘

┌─────────────┐
│    authz    │ :8181 → exposed (dev)
└─────────────┘
```

## Scalability Considerations

### Horizontal Scaling
- **BFF**: Stateless (sessions in Redis) → scale freely
- **Agent**: Stateless → scale freely
- **ACME API**: Stateless → scale freely
- **Gateway**: Envoy supports clustering
- **OPA**: Bundle distribution for policy sync
- **Redis**: Sentinel or Cluster mode

### Performance Optimizations
- JWKS caching (5 min TTL)
- Redis connection pooling
- HTTP/2 between services
- Response caching (where appropriate)
- Async I/O (FastAPI/httpx)

### Monitoring Points
- Request latency (p50, p95, p99)
- Token validation time
- OPA decision time
- Redis operation time
- Error rates per service
- Active sessions count
- Token refresh rate

## Extension Points

### Adding New APIs
1. Create new service (FastAPI + JWT validation)
2. Add cluster to `gateway/envoy.yaml`
3. Add route matching in Envoy config
4. Update OPA policy for new paths
5. Update token audience (or use resource indicators)

### Adding New Tools
1. Implement tool in `agent/app/tools.py`
2. Add node to LangGraph in `agent/app/graph.py`
3. Ensure tool receives token via state, not parameters
4. Add OPA rules if tool requires specific scopes

### Enhancing Authorization
1. Configure Okta to forward additional claims
2. Configure Envoy to pass claims to OPA via headers
3. Update `authz/policy.rego` to evaluate claims
4. Add custom business logic rules

### Adding Observability
1. Add OpenTelemetry SDK to each service
2. Configure trace propagation (traceparent header)
3. Export spans to collector (Jaeger, Tempo)
4. Add Prometheus metrics endpoints
5. Create Grafana dashboards
