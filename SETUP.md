# Detailed Setup Guide

## Okta Configuration

### 1. Create Custom Authorization Server

1. Log into your Okta Admin Console
2. Navigate to **Security → API → Authorization Servers**
3. Click **Add Authorization Server**
4. Configure:
   - **Name**: `poc`
   - **Audience**: `api://acme-api`
   - **Description**: "PoC Authorization Server for LangGraph AuthZ"

### 2. Configure Scopes

In your new authorization server:

1. Go to **Scopes** tab
2. Add the following scopes:
   - `acme.read` - Read access to ACME resources
   - `acme.write` - Write access to ACME resources

### 3. Configure Claims

In the **Claims** tab, add:

1. **Email claim**:
   - Name: `email`
   - Include in token type: Access Token
   - Value type: Expression
   - Value: `user.email`
   - Include in: Any scope

2. **Roles claim** (if using groups):
   - Name: `roles`
   - Include in token type: Access Token
   - Value type: Expression
   - Value: `Arrays.flatten(Groups.startsWith("OKTA", "app_", 10))`
   - Include in: Any scope

### 4. Create OIDC Application

1. Navigate to **Applications → Applications**
2. Click **Create App Integration**
3. Select **OIDC - OpenID Connect**
4. Choose **Web Application**
5. Configure:
   - **App integration name**: `LangGraph AuthZ PoC`
   - **Grant type**:
     - ✅ Authorization Code
     - ✅ Refresh Token
   - **Sign-in redirect URIs**:
     - `http://localhost:8080/auth/callback`
   - **Sign-out redirect URIs**:
     - `http://localhost:8080/`
   - **Controlled access**: Choose appropriate option
6. Click **Save**
7. Copy the **Client ID** and **Client secret**

### 5. Enable PKCE

1. In your app settings
2. Go to **General** tab
3. Scroll to **General Settings → Client authentication**
4. Ensure **Require PKCE** is enabled

### 6. Assign Users

1. Go to **Assignments** tab
2. Assign test users or groups to the application

### 7. Test Configuration

Your authorization server URL will be:
```
https://{yourOktaDomain}/oauth2/poc
```

Verify the discovery endpoint is accessible:
```bash
curl https://{yourOktaDomain}/oauth2/poc/.well-known/openid-configuration
```

## Environment Configuration

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Okta - replace with your actual values
OKTA_ISSUER=https://dev-12345678.okta.com/oauth2/poc
OKTA_CLIENT_ID=0oa9xyz...
OKTA_CLIENT_SECRET=abc123...
OIDC_REDIRECT_URI=http://localhost:8080/auth/callback

# Tokens/audience - should match your Okta config
ACME_AUDIENCE=api://acme-api
ACME_SCOPES=acme.read

# BFF session - generate a secure random string for production
SESSION_SECRET=your_secure_random_string_here
SESSION_COOKIE_NAME=poc_session

# Envoy/OPA - derived from OKTA_ISSUER
ENVOY_JWKS_URI=https://dev-12345678.okta.com/oauth2/poc/v1/keys
OKTA_ISSUER_HOST=dev-12345678.okta.com
OPA_URL=http://authz:8181/v1/data/policy/allow
```

### Generate Secure Session Secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Build and Run

```bash
# Start all services
make up

# Watch logs
make logs

# Stop services
make down

# Full reset
make reset
```

## Verification Steps

### 1. Check Services are Running

```bash
docker compose ps
```

All services should show "Up" status.

### 2. Run Test Suite

```bash
./test.sh
```

### 3. Manual Authentication Test

1. Open browser to http://localhost:8080/auth/login
2. You should be redirected to Okta login
3. Enter credentials for a user assigned to the app
4. After successful login, you should be redirected to http://localhost:8080/me
5. You should see JSON with your profile information

### 4. Test Agent Execution

Using browser dev tools, copy the `poc_session` cookie value, then:

```bash
curl -X POST http://localhost:8080/run-agent \
  -H "Content-Type: application/json" \
  -d '{"task": "whoami"}' \
  --cookie "poc_session=YOUR_COOKIE_VALUE"
```

Expected response:
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

### "Invalid issuer" Error

- Verify `OKTA_ISSUER` exactly matches your authorization server URL
- Include `/oauth2/poc` path if using custom authorization server
- Don't include trailing slash

### "Invalid audience" Error

- Verify `ACME_AUDIENCE=api://acme-api` matches your Okta config
- Check authorization server audience setting

### JWKS Fetch Fails

- Verify `OKTA_ISSUER_HOST` is just the hostname without protocol
- Example: `dev-12345678.okta.com` not `https://dev-12345678.okta.com`
- Verify your Okta domain is accessible from Docker containers

### OPA Always Denies

- Check OPA logs: `docker compose logs authz`
- Verify policy is loaded: `curl http://localhost:8181/v1/data/policy`
- Test policy directly:
  ```bash
  curl -X POST http://localhost:8181/v1/data/policy/allow \
    -H "Content-Type: application/json" \
    -d '{"input": {"attributes": {"request": {"http": {"method": "GET", "path": "/acme/v1/whoami", "headers": {"authorization": "Bearer test"}}}}}}'
  ```

### Session Not Found

- Redis may have restarted (sessions are in-memory)
- Re-authenticate at http://localhost:8080/auth/login
- Check Redis is running: `docker compose logs redis`

### Gateway Returns 503

- Check ACME API is running: `docker compose ps acme_api`
- Check logs: `docker compose logs gateway acme_api`
- Verify service name resolution in Docker network

## Production Considerations

Before deploying to production:

1. **Use HTTPS everywhere** - No HTTP in production
2. **Secure session secret** - Use long random value, store in secrets manager
3. **Short token TTLs** - Configure in Okta (5-15 minutes recommended)
4. **Enable refresh token rotation** - Configure in Okta app settings
5. **Implement proper CORS** - Configure in FastAPI apps
6. **Add rate limiting** - At gateway and BFF level
7. **Enable audit logging** - Log all authz decisions
8. **Add monitoring** - Prometheus metrics, health checks
9. **Implement token exchange** - For service-to-service calls (RFC 8693)
10. **Add mTLS** - Between services for additional security
11. **Enhance OPA policies** - Add fine-grained RBAC based on claims
12. **Add OpenTelemetry** - For distributed tracing
13. **Implement DPoP** - For token binding (RFC 9449)
14. **Use managed Redis** - With persistence and clustering
15. **Container security scanning** - Scan images for vulnerabilities
