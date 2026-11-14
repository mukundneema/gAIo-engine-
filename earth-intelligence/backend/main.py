"""FastAPI app. All credentials stay server-side."""
from __future__ import annotations

import logging
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

from .gemini_chat import chat as run_chat  # noqa: E402  (after load_dotenv)
from .imagery import get_historical_imagery  # noqa: E402

log = logging.getLogger("earth-intelligence")

app = FastAPI(title="Earth Intelligence API")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=30)


class ImageryRequest(BaseModel):
    place: str = Field(min_length=1, max_length=200)
    years: list[int] = Field(min_length=1, max_length=6)
    radius_km: float = 15.0


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "ee_service_account_set": bool(
            os.getenv("EARTHENGINE_SERVICE_ACCOUNT") and os.getenv("EARTHENGINE_PRIVATE_KEY")
        ),
        "ee_project": os.getenv("EARTHENGINE_PROJECT"),
    }


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    try:
        return run_chat([m.model_dump() for m in req.messages])
    except Exception as exc:
        log.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/imagery")
def imagery(req: ImageryRequest) -> dict:
    """Direct (non-chat) retrieval, handy for testing the Earth Engine setup."""
    try:
        return get_historical_imagery(req.place, req.years, req.radius_km)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("imagery failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
