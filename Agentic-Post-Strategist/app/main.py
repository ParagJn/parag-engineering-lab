from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agent_service import run_multi_agent
from app.operations import OPERATIONS
from app.schemas import GenerateRequest

app = FastAPI(title="Agentic Social Studio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Agentic Social Studio API is running."}


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/api/operations")
async def operations() -> dict:
    return {
        "operations": [
            {
                "id": key,
                "label": value["label"],
                "instruction": value["prompt"]
            }
            for key, value in OPERATIONS.items()
        ]
    }


@app.post("/api/generate")
async def generate(payload: GenerateRequest):
    try:
        return await run_multi_agent(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unhandled server error: {exc}") from exc
