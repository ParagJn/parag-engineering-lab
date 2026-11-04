"""Build Verify, offline and free (S20b): a small FastAPI project written to a temporary folder, a design with one renamed endpoint, one missing endpoint and one extra route.

    cd backend && python -m scripts.verify_demo

No model is called, nothing outside the temporary folder is read, and nothing is run.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.repos import Store
from app.verify import report as R
from app.verify.design import Design, Designed
from app.verify import match as M
from app.verify.readers import python_fastapi as PF
from app.verify.walk import walk

CODE = '''
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
router = APIRouter(prefix="/rooms")


class Booking(BaseModel):
    room_id: int
    date: str
    start_time: str
    end_time: str


@router.get("")
def list_rooms(): ...


@app.post("/api/bookings", status_code=201)
def book(body: Booking):
    raise HTTPException(status_code=409, detail="that slot is taken")


@app.get("/api/health")
def health(): ...


app.include_router(router, prefix="/api")
'''
SCHEMA = "CREATE TABLE room (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL\n);\n"

DESIGN = Design(items=[
    Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms", method="GET", path="/api/rooms"),
    Designed("API-002", "endpoint", "POST /api/reservations", "reserves a room", method="POST", path="/api/reservations",
             fields=("room_id", "date", "start_time", "end_time"), codes=(201, 400, 409)),
    Designed("API-003", "endpoint", "DELETE /api/reservations/{id}", "cancels", method="DELETE", path="/api/reservations/{id}"),
    Designed("TBL-001", "table", "rooms", "rooms: id, name, capacity", fields=("id", "name", "capacity")),
])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="verify_demo_") as tmp:
        root = Path(tmp)
        (root / "app").mkdir()
        (root / "app" / "main.py").write_text(CODE)
        (root / "app" / "schema.sql").write_text(SCHEMA)
        (root / ".env").write_text("SECRET=never-read\n")
        walked = walk(str(root))
        backend = PF.read_backend([(f.path, f.text) for f in walked.files])
        matched = M.match_all(DESIGN, backend)
        print(R.markdown(R.build_report(matched.matches, matched.extras, [f"backend: {s}" for s in walked.skipped])))
        print("Stored runs are kept in the database; this demo does not write one.")


if __name__ == "__main__":
    main()
