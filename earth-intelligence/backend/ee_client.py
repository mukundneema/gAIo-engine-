"""Earth Engine initialisation.

On Vercel (or any unattended server) we authenticate with a service account.
Locally, if no service-account variables are set, we fall back to the
credentials created by `earthengine authenticate`.
"""
from __future__ import annotations

import json
import os
import threading

import ee

_EE_SCOPE = "https://www.googleapis.com/auth/earthengine"
_lock = threading.Lock()
_ready = False


def _service_account_info(email: str, key: str) -> dict:
    """Accept either the full JSON key file contents or just the PEM private key."""
    key = key.strip()
    if key.startswith("{"):
        info = json.loads(key)
        info.setdefault("client_email", email)
        return info
    return {
        "type": "service_account",
        "client_email": email,
        # Env var UIs often store newlines as literal "\n".
        "private_key": key.replace("\\n", "\n"),
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def init_ee() -> None:
    """Initialise Earth Engine once per process."""
    global _ready
    if _ready:
        return
    with _lock:
        if _ready:
            return
        project = os.getenv("EARTHENGINE_PROJECT") or None
        email = os.getenv("EARTHENGINE_SERVICE_ACCOUNT")
        key = os.getenv("EARTHENGINE_PRIVATE_KEY")

        if email and key:
            from google.oauth2 import service_account

            info = _service_account_info(email, key)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=[_EE_SCOPE]
            )
            ee.Initialize(credentials=creds, project=project)
        else:
            ee.Initialize(project=project)
        _ready = True
