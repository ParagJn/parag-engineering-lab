from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import SlotConfig, Settings, get_settings
from .llm.gateway import Gateway
from .llm.providers.base import Provider
from .llm.providers.ica import IcaProvider
from .llm.providers.recording import RecordingProvider, ReplayProvider
from .llm.providers.unwired import UnwiredProvider
from .llm.recordings import RecordingStore, recordings_mode
from .llm.routing import Routing
from .llm.status import gateway_status
from .agents.runtime import AgentRuntime
from .agents.skills import SkillLibrary
from .agents.status import skills_status
from .context.status import context_status
from .repos import Store
from .guardrails.status import guardrails_status
from .review.human import HumanActions
from .routes import router
from .routes_artefacts import router as artefacts_router
from .routes_content import router as content_router
from .routes_projects import router as projects_router
from .routes_review import router as review_router
from .routes_trace import router as trace_router
from .run.events import EventBus
from .run.runner import PhaseRunner
from .run.status import run_status
from .review.prompt import load_rubric
from .review.service import ReviewService
from .review.status import review_status
from .workflow.definitions import load_catalogue
from .workflow.engine import WorkflowEngine
from .workflow.status import workflow_status

CORS_ORIGINS = ["http://localhost:5270", "http://127.0.0.1:5270"]


def _slot_payload(slot: SlotConfig) -> dict:
    return {
        "slot": slot.name,
        "model_id": slot.model_id,
        "fallback_model_id": slot.fallback_model_id,
        "price_input": slot.price_input,
        "price_output": slot.price_output,
        "priced": slot.priced,
    }


def choose_provider(cfg: Settings, recordings: RecordingStore | None = None) -> Provider:
    """Replay serves saved replies and needs no credentials. Live needs them, and may also record."""
    if cfg.app_mode == "replay":
        return ReplayProvider(recordings or RecordingStore(cfg.recordings_path), pace=cfg.replay_pace)
    if cfg.endpoint_set and cfg.api_key_set:
        ica = IcaProvider(cfg)  # builds a client; makes no network call
        if cfg.record_live_calls:
            return RecordingProvider(ica, recordings or RecordingStore(cfg.recordings_path), cfg)
        return ica
    return UnwiredProvider()


def create_app(settings: Settings | None = None, provider: Provider | None = None) -> FastAPI:
    """Build the API. Settings are read here, not at import, so tests can inject their own."""
    cfg = settings or get_settings()
    store = Store.open(cfg.db_path, limits=cfg.context_limits)
    routing = Routing.load()  # a broken routing file stops startup with a clear message
    catalogue = load_catalogue(routing.roles.keys())  # so does a broken phase definition
    engine = WorkflowEngine(catalogue, store)
    skills = SkillLibrary.load(catalogue)  # a broken skill file stops startup, naming the file and line
    recordings = RecordingStore(cfg.recordings_path) if recordings_mode(cfg) in ("replay", "recording") else None
    chosen = provider or choose_provider(cfg, recordings)
    gateway = Gateway(cfg, routing, chosen, store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        close = getattr(chosen, "aclose", None)
        if close is not None:
            await close()

    app = FastAPI(title="SDLC Workbench API", lifespan=lifespan)
    app.state.store = store
    app.state.gateway = gateway
    app.state.engine = engine
    app.state.skills = skills
    app.state.agents = AgentRuntime(cfg, store, gateway, catalogue, engine, skills)
    scanner = app.state.agents.scanner                 # the one scanner every enforcement point shares
    store.artefacts.backstop = scanner                  # last-line refusal of a high-confidence secret on every new version
    store.context.scanner = scanner                     # uploaded documents are scanned and flagged, never blocked
    rubric = load_rubric()  # a broken rubric stops startup, like a broken skill
    app.state.reviews = ReviewService(cfg, store, gateway, app.state.agents, engine, rubric)
    app.state.human = HumanActions(store, engine, app.state.agents, app.state.reviews)
    store.runs.interrupt_unfinished()  # runs left "running" by a process that no longer exists
    bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
    app.state.bus = bus
    app.state.settings = cfg
    app.state.runner = PhaseRunner(cfg, store, engine, app.state.agents, app.state.reviews, bus)
    app.include_router(router)
    app.include_router(projects_router)
    app.include_router(content_router)
    app.include_router(artefacts_router)
    app.include_router(review_router)
    app.include_router(trace_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict:
        """Shows what configuration loaded. Never returns the key, the endpoint URL or a file path."""
        return {
            "mode": cfg.app_mode,
            "endpoint_set": cfg.endpoint_set,
            "api_key_set": cfg.api_key_set,
            "slots": [_slot_payload(slot) for slot in cfg.slots.values()],
            "db": {
                "schema_version": store.db.schema_version,
                "projects": store.projects.count(),
            },
            "gateway": gateway_status(cfg, routing, gateway.provider.label, recordings),
            "workflow": workflow_status(catalogue),
            "context": context_status(store.context.limits),
            "skills": skills_status(catalogue, skills),
            "review": review_status(routing, rubric),
            "run": run_status(cfg, app.state.runner.active_count, bus.watcher_count),
            "guardrails": guardrails_status(scanner),
        }

    return app
