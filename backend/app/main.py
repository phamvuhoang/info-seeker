from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .api import health, search
from .core.config import settings
from .services.sse_manager import progress_manager
import logging
import json
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# SSE endpoint for real-time progress updates
@app.get("/sse/{session_id}")
async def sse_endpoint(session_id: str):
    """Server-Sent Events endpoint for real-time search progress updates"""

    async def event_stream():
        # Register the session for SSE updates
        await progress_manager.connect(session_id)

        try:
            while True:
                # Check for new messages for this session
                message = await progress_manager.get_message(session_id)
                if message:
                    # Format as SSE
                    yield f"data: {json.dumps(message)}\n\n"
                else:
                    # Send heartbeat to keep connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

                # Wait a bit before checking again
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"SSE error for session {session_id}: {e}")
        finally:
            progress_manager.disconnect(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
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