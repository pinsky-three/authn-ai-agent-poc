from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    okta_issuer: str
    acme_audience: str

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
