"""
BharatSahayak — Phase 9 UI Server
===================================
Minimal FastAPI bridge: serves the farmer-facing frontend and delegates
all agent execution to the sealed Phase 8 ADK backend.

Backend files (app/) are NOT touched.
Run:  uv run frontend/server.py
URL:  http://127.0.0.1:18082
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

# Ensure the project root (bharatsahayak/) is on the path so we can
# import `app` without installing the package.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent  # sealed — not modified

# ── Shared session service and runner ────────────────────────────────────────
_session_service = InMemorySessionService()
_runner = Runner(
    agent=root_agent,
    session_service=_session_service,
    app_name="app",
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
web = FastAPI(title="BharatSahayak UI", docs_url=None, redoc_url=None)
web.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ─────────────────────────────────────────────────────────────

class SessionRequest(BaseModel):
    user_id: str | None = None
    language: str | None = None



class ResumeInput(BaseModel):
    interrupt_id: str = "more_info"
    result: str = ""


class RunRequest(BaseModel):
    session_id: str
    user_id: str
    message: str | None = None
    resume: ResumeInput | None = None
    language: str | None = None


# ── Event serializer ──────────────────────────────────────────────────────────

def _serialize_event(event) -> dict:
    """Convert an ADK Event into a JSON-serializable dict.
    
    Only scalar-safe fields are included.  The farmer UI uses this data
    through the presentation-layer adapter (parseAdkEventStream) in app.js
    and never directly renders raw events.
    """
    out: dict = {
        "author": getattr(event, "author", None),
        "output": None,
        "content": None,
    }

    raw_output = getattr(event, "output", None)
    if isinstance(raw_output, str):
        out["output"] = raw_output

    if event.content is not None:
        content: dict = {"role": event.content.role, "parts": []}
        for part in event.content.parts or []:
            p: dict = {}
            if part.text is not None:
                p["text"] = part.text
            if part.function_call is not None:
                fc = part.function_call
                p["functionCall"] = {
                    "name": fc.name,
                    "id": getattr(fc, "id", None),
                    "args": dict(fc.args) if fc.args else {},
                }
            if part.function_response is not None:
                fr = part.function_response
                p["functionResponse"] = {
                    "name": fr.name,
                    "id": getattr(fr, "id", None),
                    "response": dict(fr.response) if fr.response else {},
                }
            if p:
                content["parts"].append(p)
        out["content"] = content

    return out


# ── API routes ────────────────────────────────────────────────────────────────

@web.post("/api/session")
async def create_session(req: SessionRequest = None):
    """Create a new ADK session.  Returns session_id and user_id."""
    user_id = (req.user_id if req else None) or str(uuid.uuid4())
    session = _session_service.create_session_sync(
        user_id=user_id, app_name="app"
    )
    if req and req.language:
        lang_name = "Hindi" if req.language.lower().startswith("hi") else "English"
        session.state["ui_language"] = lang_name
    return {"session_id": session.id, "user_id": user_id}



@web.post("/api/run")
async def run_agent(req: RunRequest):
    """Run one conversational turn and return all serialized ADK events.

    The frontend adapter (parseAdkEventStream) is responsible for reducing
    this list to exactly one farmer-facing message or HITL card.
    """
    try:
        if req.resume:
            part = types.Part(
                function_response=types.FunctionResponse(
                    name="adk_request_input",
                    id=req.resume.interrupt_id,
                    response={"result": req.resume.result},
                )
            )
            new_message = types.Content(role="user", parts=[part])
        elif req.message is not None:
            new_message = types.Content(
                role="user",
                parts=[types.Part.from_text(text=req.message)],
            )
        else:
            raise HTTPException(status_code=400, detail="'message' or 'resume' is required")

        events: list[dict] = []
        async for event in _runner.run_async(
            user_id=req.user_id,
            session_id=req.session_id,
            new_message=new_message,
        ):
            events.append(_serialize_event(event))

        return JSONResponse(content=events)

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Log internally; never expose stack traces to the farmer UI.
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": str(exc)},
        )


# ── Static file serving ───────────────────────────────────────────────────────
_frontend_dir = os.path.dirname(os.path.abspath(__file__))


@web.get("/")
async def serve_index():
    """Serve the farmer UI index page."""
    return FileResponse(os.path.join(_frontend_dir, "index.html"))


# Mount remaining static assets (CSS, JS, images).
# This must come AFTER explicit API routes so /api/* is not intercepted.
web.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("UI_PORT", 8080)))
    print(f"\n  BharatSahayak Farmer UI -> http://{host}:{port}\n")
    uvicorn.run(web, host=host, port=port, log_level="warning")
