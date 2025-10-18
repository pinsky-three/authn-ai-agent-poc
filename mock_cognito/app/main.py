"""
Mock Cognito Service for PoC Testing

Simulates AWS Cognito with:
- User authentication
- JWT token generation with custom claims
- User pools and identity pools
- OIDC-like endpoints (.well-known/jwks.json)
"""
import jwt
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 9000
    jwt_secret: str = "mock-jwt-secret-change-in-production"
    jwt_issuer: str = "http://mock-cognito:9000"
    jwt_audience: str = "api://acme-api"
    jwt_expiry_minutes: int = 60


settings = Settings()
app = FastAPI(title="Mock Cognito Service", version="1.0.0")


# Mock user database
MOCK_USERS = {
    "testuser@example.com": {
        "password": "TestPassword123!",
        "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "email": "testuser@example.com",
        "email_verified": True,
        "custom:team": "platform",
        "custom:project": "poc",
        "custom:env": "dev",
        "custom:cost_center": "engineering",
        "cognito:groups": ["developers", "poc-team"],
    },
    "admin@example.com": {
        "password": "AdminPass456!",
        "sub": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "email": "admin@example.com",
        "email_verified": True,
        "custom:team": "platform",
        "custom:project": "poc",
        "custom:env": "prod",
        "custom:cost_center": "engineering",
        "cognito:groups": ["admins", "developers"],
    },
}

# Mock tokens storage (for introspection)
ACTIVE_TOKENS: Dict[str, dict] = {}


class AuthRequest(BaseModel):
    username: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AssumeRoleRequest(BaseModel):
    id_token: str = Field(..., description="Cognito ID token")
    role_arn: str = Field(..., description="IAM role ARN to assume")
    session_name: Optional[str] = Field(None, description="Session name")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock-cognito"}


@app.get("/.well-known/jwks.json")
async def jwks():
    """Mock JWKS endpoint (simplified - returns empty keys)"""
    return {
        "keys": [
            {
                "kid": "mock-key-id-1",
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": "mock-modulus",
                "e": "AQAB",
            }
        ]
    }


@app.get("/.well-known/openid-configuration")
async def openid_config():
    """Mock OpenID configuration"""
    return {
        "issuer": settings.jwt_issuer,
        "authorization_endpoint": f"{settings.jwt_issuer}/oauth2/authorize",
        "token_endpoint": f"{settings.jwt_issuer}/oauth2/token",
        "userinfo_endpoint": f"{settings.jwt_issuer}/oauth2/userInfo",
        "jwks_uri": f"{settings.jwt_issuer}/.well-known/jwks.json",
        "response_types_supported": ["code", "token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
    }


@app.post("/auth/login", response_model=TokenResponse)
async def login(auth_req: AuthRequest):
    """
    Authenticate user and return tokens

    Simulates Cognito InitiateAuth / AdminInitiateAuth
    """
    user = MOCK_USERS.get(auth_req.username)

    if not user or user["password"] != auth_req.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    now = int(time.time())
    expiry = now + (settings.jwt_expiry_minutes * 60)

    # Create access token
    access_token_payload = {
        "sub": user["sub"],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": expiry,
        "token_use": "access",
        "scope": "openid profile email",
        "username": auth_req.username,
    }

    # Create ID token with custom claims
    id_token_payload = {
        "sub": user["sub"],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": expiry,
        "token_use": "id",
        "email": user["email"],
        "email_verified": user["email_verified"],
        "custom:team": user.get("custom:team"),
        "custom:project": user.get("custom:project"),
        "custom:env": user.get("custom:env"),
        "custom:cost_center": user.get("custom:cost_center"),
        "cognito:groups": user.get("cognito:groups", []),
    }

    # Create refresh token (simplified)
    refresh_token = str(uuid.uuid4())

    # Sign tokens
    access_token = jwt.encode(access_token_payload, settings.jwt_secret, algorithm="HS256")
    id_token = jwt.encode(id_token_payload, settings.jwt_secret, algorithm="HS256")

    # Store for introspection
    ACTIVE_TOKENS[access_token] = {
        "active": True,
        "payload": access_token_payload,
        "created_at": now,
    }

    return TokenResponse(
        access_token=access_token,
        id_token=id_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_expiry_minutes * 60,
    )


@app.post("/auth/assume-role")
async def assume_role(req: AssumeRoleRequest):
    """
    Simulate AWS STS AssumeRoleWithWebIdentity

    Takes Cognito ID token and returns AWS-like temporary credentials
    """
    try:
        # Verify and decode ID token
        payload = jwt.decode(
            req.id_token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
        )

        if payload.get("token_use") != "id":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token must be an ID token",
            )

        # Extract session tags from custom claims
        session_tags = {
            "team": payload.get("custom:team"),
            "project": payload.get("custom:project"),
            "env": payload.get("custom:env"),
            "cost_center": payload.get("custom:cost_center"),
        }

        # Generate mock AWS credentials
        session_name = req.session_name or f"cognito-{payload['sub'][:8]}"

        credentials = {
            "AccessKeyId": f"ASIA{uuid.uuid4().hex[:16].upper()}",
            "SecretAccessKey": f"mock/{uuid.uuid4().hex}",
            "SessionToken": jwt.encode(
                {
                    "sub": payload["sub"],
                    "role_arn": req.role_arn,
                    "session_name": session_name,
                    "session_tags": session_tags,
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 3600,
                },
                settings.jwt_secret,
                algorithm="HS256",
            ),
            "Expiration": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
        }

        assumed_role_user = {
            "AssumedRoleId": f"AROA{uuid.uuid4().hex[:16].upper()}:{session_name}",
            "Arn": f"arn:aws:sts::000000000000:assumed-role/{req.role_arn.split('/')[-1]}/{session_name}",
        }

        return {
            "Credentials": credentials,
            "AssumedRoleUser": assumed_role_user,
            "SubjectFromWebIdentityToken": payload["sub"],
            "SessionTags": [
                {"Key": k, "Value": v} for k, v in session_tags.items() if v
            ],
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )


@app.post("/auth/introspect")
async def introspect_token(token: str):
    """Token introspection endpoint (for revocation checks)"""
    token_data = ACTIVE_TOKENS.get(token)

    if not token_data:
        return {"active": False}

    # Check expiration
    if token_data["payload"]["exp"] < int(time.time()):
        return {"active": False}

    return {
        "active": True,
        "sub": token_data["payload"]["sub"],
        "username": token_data["payload"].get("username"),
        "exp": token_data["payload"]["exp"],
        "iat": token_data["payload"]["iat"],
        "scope": token_data["payload"].get("scope"),
    }


@app.post("/auth/revoke")
async def revoke_token(token: str):
    """Revoke a token (for testing immediate revocation)"""
    if token in ACTIVE_TOKENS:
        ACTIVE_TOKENS[token]["active"] = False
        return {"message": "Token revoked successfully"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Token not found",
    )


@app.get("/users")
async def list_users():
    """List mock users (for testing/debugging only)"""
    return {
        "users": [
            {
                "username": username,
                "email": user["email"],
                "sub": user["sub"],
                "attributes": {
                    k: v for k, v in user.items()
                    if k.startswith("custom:") or k == "cognito:groups"
                }
            }
            for username, user in MOCK_USERS.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
