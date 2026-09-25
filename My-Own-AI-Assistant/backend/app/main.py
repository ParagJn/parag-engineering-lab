"""Main FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .routers import attachments_router, messages_router, sessions_router
from .svg_api import router as svg_router

# INFO-level logging so streaming diagnostics (see ibm_ica_client.chat_stream)
# show up in the console, not just ERROR-level tracebacks.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# Ensure directories exist
config.ensure_directories()

# Create FastAPI app
app = FastAPI(
    title="AI Assistant API",
    description="Personal AI Assistant with document and image support",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions_router, prefix=config.API_PREFIX)
app.include_router(messages_router, prefix=config.API_PREFIX)
app.include_router(attachments_router, prefix=config.API_PREFIX)
app.include_router(svg_router, prefix=config.API_PREFIX)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AI Assistant API",
        "version": "1.0.0",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
