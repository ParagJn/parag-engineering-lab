from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_config
from .services.sap_client import SAPAIClient
from .services.agent_service import AgentService
from .services.session_service import SessionService
from .routes import sessions, interview, dashboard


def create_app() -> FastAPI:
    config = get_config()

    app = FastAPI(
        title="Interview Coach API",
        version="1.0.0",
        description="AI-powered multi-agent interview preparation platform",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config["app"]["cors_origins"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Instantiate services
    sap_client = SAPAIClient(config["sap_ai_core"])
    agent_service = AgentService(sap_client, config)
    session_service = SessionService(config["app"]["sessions_dir"])

    # Attach to app state for dependency injection
    app.state.sap_client = sap_client
    app.state.agent_service = agent_service
    app.state.session_service = session_service
    app.state.config = config

    # Routers
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": config["app"]["version"]}

    return app


app = create_app()
