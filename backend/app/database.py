import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

def get_engine():
    primary_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    fallback_url = os.getenv("SQLITE_FALLBACK_URL", settings.SQLITE_FALLBACK_URL)
    
    # Try primary PostgreSQL database first
    if primary_url.startswith("postgresql"):
        try:
            test_engine = create_engine(
                primary_url,
                connect_args={"connect_timeout": 2},
                pool_pre_ping=True
            )
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(f"Connected successfully to PostgreSQL database: {primary_url.split('@')[-1]}")
            return test_engine
        except Exception as e:
            logger.warning(
                f"Could not connect to PostgreSQL ({e}). Falling back to local database: {fallback_url}"
            )
            return create_engine(
                fallback_url,
                connect_args={"check_same_thread": False} if fallback_url.startswith("sqlite") else {}
            )
    else:
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
