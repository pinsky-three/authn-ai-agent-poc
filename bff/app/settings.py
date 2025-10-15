from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    okta_issuer: str
    okta_client_id: str
    okta_client_secret: str
    oidc_redirect_uri: str
    acme_audience: str
    acme_scopes: str = "acme.read"
    session_secret: str
    session_cookie_name: str = "poc_session"
    redis_url: str = "redis://redis:6379/0"

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
