from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .api import health, search, database, predefined_content
from .core.config import settings
from .core.connection_manager import cleanup_connections
from .core.migrations import migration_manager
from .services.sse_manager import progress_manager
from .services.scheduler_service import scheduler_service
from .scrapers.engine import scraping_engine
from .scrapers.agoda_scraper import AgodaScraper
from .scrapers.tabelog_scraper import TabelogScraper
import logging
import json
import asyncio
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app with lifecycle events
app = FastAPI(
    title=settings.app_name,
    description="InfoSeeker - AI-powered search platform for junk-free, personalized information retrieval",
    version=settings.app_version,
    debug=settings.debug
)

# Add startup and shutdown events for proper resource management
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    logger.info("InfoSeeker backend starting up...")

    # Run database migrations
    logger.info("Running database migrations...")
    try:
        migration_success = await migration_manager.run_migrations()
        if migration_success:
            logger.info("Database migrations completed successfully")
        else:
            logger.error("Database migrations failed - some features may not work correctly")
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        # Don't fail startup, but log the error
        logger.warning("Application starting without migrations - some features may not work correctly")

    # Register scrapers with the scraping engine
    logger.info("Registering scrapers...")
    try:
        scraping_engine.register_scraper('agoda', AgodaScraper)
        scraping_engine.register_scraper('tabelog', TabelogScraper)
        logger.info("Scrapers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register scrapers: {e}")

    # Initialize and start scheduler for scraping tasks
    logger.info("Starting scheduler service...")
    try:
        await scheduler_service.start()
        logger.info("Scheduler service started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler service: {e}")
        logger.warning("Application starting without scheduler - scraping tasks will not run automatically")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    logger.info("InfoSeeker backend shutting down...")

    # Stop scheduler service
    try:
        await scheduler_service.stop()
        logger.info("Scheduler service stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler service: {e}")

    # Cleanup scraping engine
    try:
        await scraping_engine.cleanup()
        logger.info("Scraping engine cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up scraping engine: {e}")

    # Cleanup other connections
    await cleanup_connections()
    logger.info("Cleanup completed")

# Register cleanup function for process termination
atexit.register(lambda: asyncio.run(cleanup_connections()))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE endpoint for real-time progress updates
@app.get("/sse/{session_id}")
async def sse_endpoint(session_id: str):
    """Server-Sent Events endpoint for real-time search progress updates"""
    logger.info(f"SSE connection requested for session: {session_id}")

    async def event_stream():
        # Register the session for SSE updates
        await progress_manager.connect(session_id)
        logger.info(f"SSE session connected: {session_id}")

        try:
            heartbeat_counter = 0
            while True:
                # Check for new messages for this session
                message = await progress_manager.get_message(session_id)
                if message:
                    logger.info(f"SSE sending message for {session_id}: {message.get('type', 'unknown')}")
                    # Format as SSE
                    yield f"data: {json.dumps(message)}\n\n"
                    heartbeat_counter = 0  # Reset heartbeat counter when we send real data
                else:
                    # Send heartbeat every 10 iterations (5 seconds) to keep connection alive
                    heartbeat_counter += 1
                    if heartbeat_counter >= 10:
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                        heartbeat_counter = 0

                # Wait a bit before checking again
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"SSE error for session {session_id}: {e}")
        finally:
            progress_manager.disconnect(session_id)
            logger.info(f"SSE session disconnected: {session_id}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "Access-Control-Allow-Methods": "GET, OPTIONS"
        }
    )

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(database.router, prefix="/api/v1/database", tags=["database"])
app.include_router(predefined_content.router, prefix="/api/v1/predefined_content", tags=["predefined_content"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )