import logging
from fastapi import FastAPI
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Inkloom AI — Standalone Pre-Publication Brand Governance & Content Integrity Platform",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
origins = settings.cors_origins_list
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
        "docs": "/docs",
        "version": settings.VERSION
    }
