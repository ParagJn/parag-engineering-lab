"""
Profile Generator — FastAPI backend
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env from project root (one level up from backend/)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Profile Generator backend starting…")
    yield
    logger.info("Profile Generator backend shutting down.")


app = FastAPI(
    title="Profile Generator API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import upload as upload_router
from routers import generate as generate_router

app.include_router(upload_router.router, prefix="/api", tags=["upload"])
app.include_router(generate_router.router, prefix="/api", tags=["generate"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Profile Generator API"}
