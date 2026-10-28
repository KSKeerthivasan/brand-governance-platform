import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.api.v1 import api_v1_router
# Import all models to ensure metadata is populated
import app.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inkloom")

# Initialize database schema tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production deployment safeguards validation (Milestone 5E)
    startup_errors = settings.validate_production_readiness()
    if startup_errors:
        error_msg = "FATAL: Application failed security startup checks:\n" + "\n".join(f"- {e}" for e in startup_errors)
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    yield

# Configure interactive documentation URLs (disabled in production)
docs_url = None if settings.ENVIRONMENT.lower() == "production" else "/docs"
redoc_url = None if settings.ENVIRONMENT.lower() == "production" else "/redoc"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Inkloom AI — Standalone Pre-Publication Brand Governance & Content Integrity Platform",
    docs_url=docs_url,
    redoc_url=redoc_url,
    lifespan=lifespan
)

# Unhandled exception sanitization for production security
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    if settings.ENVIRONMENT.lower() == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error. Incident has been recorded for review."}
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)}
    )

# CORS Configuration
origins = settings.cors_origins_list
if settings.ENVIRONMENT.lower() != "production":
    if "*" not in origins and "http://localhost:5173" not in origins:
        origins.append("http://localhost:5173")
    if "http://127.0.0.1:5173" not in origins:
        origins.append("http://127.0.0.1:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database_engine": engine.name
    }

@app.get("/")
def root():
    return {
        "message": "Inkloom AI Brand-Governance API is running.",
        "docs": docs_url or "disabled in production",
        "version": settings.VERSION
    }
