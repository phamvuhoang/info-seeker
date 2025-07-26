from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import health, search
from .core.config import settings

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="InfoSeeker - AI-powered search platform for junk-free, personalized information retrieval",
    version=settings.app_version,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )