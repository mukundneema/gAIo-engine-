"""Place name -> coordinates, via OpenStreetMap Nominatim."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires an identifying User-Agent.
USER_AGENT = "earth-intelligence/0.1 (satellite land-cover explorer)"


@dataclass
class Place:
    name: str
    lat: float
    lon: float


def geocode(query: str) -> Place:
    resp = httpx.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=10.0,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not find a location matching '{query}'.")
    top = results[0]
    return Place(
        name=top.get("display_name", query),
        lat=float(top["lat"]),
        lon=float(top["lon"]),
    )
