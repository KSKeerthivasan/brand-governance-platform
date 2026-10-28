import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Inkloom AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOW_DEV_LOGIN: bool = True  # Allowed in local development, strictly forbidden in production
    RATE_LIMIT_FAILED_LOGINS: int = 5
    RATE_LIMIT_LOCKOUT_SECONDS: int = 300
    
    SECRET_KEY: str = "inkloom-dev-secret-key-super-secure-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/inkloom_ai"
    
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = "./storage_data"
    
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_STORAGE_BUCKET: str = "inkloom-private-assets"
    
    ENABLE_EXTERNAL_AI: bool = False
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def validate_production_readiness(self) -> List[str]:
        """
        Validates deployment configuration. If environment is production,
        returns list of critical security violations that prevent application startup.
        """
        errors = []
        is_prod = self.ENVIRONMENT.lower() == "production"
        if is_prod:
            if self.ALLOW_DEV_LOGIN:
                errors.append("ALLOW_DEV_LOGIN cannot be True in production environment.")
            if self.DEBUG:
                errors.append("DEBUG mode cannot be enabled in production environment.")
            
            # Secret key checks
            insecure_key_patterns = ["dev", "secret", "change_me", "default", "password", "test"]
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32 or any(pat in self.SECRET_KEY.lower() for pat in insecure_key_patterns):
                errors.append("SECRET_KEY must be a cryptographically secure string (at least 32 characters, no predictable substrings) in production.")
            
            # Database connection checks
            db_url_lower = (self.DATABASE_URL or "").lower()
            if "sqlite" in db_url_lower:
                errors.append("Production database cannot use SQLite. A production PostgreSQL instance must be configured.")
            if "postgres:postgres@localhost" in db_url_lower or "postgres:postgres@127.0.0.1" in db_url_lower:
                errors.append("Production database cannot use default local development database credentials (postgres:postgres@localhost).")
            
            # CORS origins checks
            origins = self.cors_origins_list
            if not origins:
                errors.append("CORS_ORIGINS must specify at least one explicit allowed origin in production environment.")
            if "*" in origins:
                errors.append("CORS_ORIGINS cannot contain wildcard ('*') in production environment.")
            
            # Storage persistence checks
            if self.STORAGE_BACKEND == "local":
                if not self.LOCAL_STORAGE_DIR or self.LOCAL_STORAGE_DIR.strip() in ("", "/tmp", "./tmp", "tmp"):
                    errors.append("LOCAL_STORAGE_DIR must specify a persistent directory path in production.")
            elif self.STORAGE_BACKEND == "supabase":
                if not self.SUPABASE_URL or not self.SUPABASE_SERVICE_KEY:
                    errors.append("Supabase storage requires SUPABASE_URL and SUPABASE_SERVICE_KEY in production.")
        return errors

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
            ".env"
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
