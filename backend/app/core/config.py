"""Central configuration settings for WiFiRouter backend."""
import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "WiFiRouter Management Platform"
    APP_VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Secret keys
    SECRET_KEY: str = os.environ.get("WIFIROUTER_SECRET_KEY", "wifirouter-super-secret-jwt-session-key-change-in-production")
    AGENT_SECRET: str = os.environ.get("WIFIROUTER_AGENT_SECRET", "wifirouter-dev-insecure-agent-secret-key-32b")
    AGENT_BASE_URL: str = os.environ.get("WIFIROUTER_AGENT_URL", "http://127.0.0.1:8091")
    
    CAPTIVE_PROXY_SECRET: str = os.environ.get("WIFIROUTER_CAPTIVE_SECRET", "")

    # Database URL: default to SQLite for instant local dev & tests; production uses PostgreSQL
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./wifirouter.db")
    
    # Session expiration (minutes)
    SESSION_EXPIRE_MINUTES: int = 480  # 8 hours
    IDLE_TIMEOUT_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8090",
        "http://127.0.0.1:8090",
        "http://192.168.16.2:8090",
        "https://192.168.16.2:8090"
    ]
    
    # Default admin credentials for initial setup
    DEFAULT_ADMIN_USER: str = os.environ.get("WIFIROUTER_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.environ.get("WIFIROUTER_ADMIN_PASSWORD", "admin12345678")
    
    # Server Binding
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8090"))
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

