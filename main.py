"""
BRD to Jira Application - FastAPI Backend
Main application entry point with CORS configuration
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.api.v1 import documents, requirements, gantt, jira, assignments, jira_sync
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    setup_logging()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="BRD to Jira Application",
    description="Process BRD documents and create Jira tickets with Gantt charts",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration (use central settings and trim whitespace)
#origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

origins = os.getenv("ALLOWED_ORIGINS")
if isinstance(origins, str):
    cors_origins = [origins.strip()]
else:
    cors_origins = [origin.strip() for origin in origins]

# Add local development origins
origins.extend([
    "https://userstorymapping.tngrm.ai/",
    "https://user-story-mapping-frontend.vercel.app/",
    "http://localhost:3000"  # For local development
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploaded documents
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API routes
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(requirements.router, prefix="/api/v1/requirements", tags=["requirements"])
app.include_router(gantt.router, prefix="/api/v1/gantt", tags=["gantt"])
app.include_router(jira.router, prefix="/api/v1/jira", tags=["jira"])
app.include_router(assignments.router, prefix="/api/v1/assignments", tags=["assignments"])
app.include_router(jira_sync.router, prefix="/api/v1/jira-sync", tags=["jira-sync"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "BRD to Jira Application API", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.ENVIRONMENT == "development" else False
    )

