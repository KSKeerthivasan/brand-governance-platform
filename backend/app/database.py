import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

def get_engine():
    primary_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    
    if primary_url.startswith("postgresql"):
        try:
            db_engine = create_engine(
                primary_url,
                connect_args={"connect_timeout": 5},
                pool_pre_ping=True
            )
            with db_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            # Mask credentials when logging host/database
            target_info = primary_url.split("@")[-1] if "@" in primary_url else primary_url
            logger.info(f"Connected successfully to PostgreSQL database at: {target_info}")
            return db_engine
        except Exception as e:
            target_info = primary_url.split("@")[-1] if "@" in primary_url else "configured host"
            error_msg = (
                f"Failed to connect to configured PostgreSQL database ({target_info}): {e}. "
                "Silent SQLite fallback is disabled. Please verify that the PostgreSQL instance is running, "
                "accessible, and that credentials and network policies are correctly configured in .env."
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
    else:
        # SQLite used only when explicitly configured (e.g. isolated test environments)
        logger.info(f"Using database engine: {primary_url}")
        return create_engine(
            primary_url,
            connect_args={"check_same_thread": False} if primary_url.startswith("sqlite") else {}
        )

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
