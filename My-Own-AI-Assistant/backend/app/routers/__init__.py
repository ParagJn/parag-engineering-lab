"""API routers."""

from .attachments import files_router as attachment_files_router
from .attachments import router as attachments_router
from .messages import router as messages_router
from .projects import router as projects_router
from .search import router as search_router
from .sessions import router as sessions_router

__all__ = [
    "attachment_files_router",
    "attachments_router",
    "messages_router",
    "projects_router",
    "search_router",
    "sessions_router",
]
