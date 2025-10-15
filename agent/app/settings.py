from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gateway_url: str = "http://gateway:8000"

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
