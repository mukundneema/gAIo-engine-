"""Turn a plain-English request into (place, years, radius) without any AI model.

Handles things like:
  "Show me Mumbai in 2016, 2020, and 2025"
  "How has Dubai's built-up area changed between 2017 and 2024?"
  "Las Vegas 2018-2025 within 20 km"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_RANGE = re.compile(r"\b(20\d{2})\s*(?:-|–|—|to|through|until|till)\s*(20\d{2})\b", re.I)
_YEAR = re.compile(r"\b(20\d{2})\b")
_RADIUS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:km|kms|kilometers?|kilometres?)\b", re.I)
_FORECAST_WORDS = re.compile(
    r"\b(predict|prediction|forecast|future|will look|will be|going to look)\b", re.I
)

# Words trimmed from the START and END of what is left after removing years.
_STOP = {
    "show", "me", "can", "you", "please", "i", "want", "to", "see", "view", "look", "at",
    "compare", "comparison", "how", "has", "have", "did", "does", "do", "changed", "change",
    "between", "and", "from", "in", "for", "during", "over", "the", "a", "an", "of", "on",
    "satellite", "image", "images", "imagery", "land", "cover", "landcover", "map", "maps",
    "growth", "urban", "built-up", "builtup", "built", "up", "area", "areas", "through",
    "until", "till", "vs", "versus", "with", "what", "happened", "history", "historical",
    "evolution", "expansion", "across", "within", "radius", "around", "near", "over", "time",
    "is", "was", "were", "get", "give", "pull", "up", "stats", "statistics", "then", "now",
    "years", "year", "x", "or", "also", "too",
    "hello", "hi", "hey", "thanks", "thank", "ok", "okay", "yes", "no", "help",
}


@dataclass
class ParsedRequest:
    place: str = ""
    years: list[int] = field(default_factory=list)
    radius_km: float | None = None
    future_years: list[int] = field(default_factory=list)
    wants_forecast: bool = False


def _expand_range(start: int, end: int) -> list[int]:
    if start > end:
        start, end = end, start
    years = {start, end}
    if end - start >= 4:
        years.add(round((start + end) / 2))
    return sorted(years)


def parse_request(text: str, today: date | None = None) -> ParsedRequest:
    this_year = (today or date.today()).year
    out = ParsedRequest()
    out.wants_forecast = bool(_FORECAST_WORDS.search(text))

    years: set[int] = set()

    def take_range(m: re.Match) -> str:
        years.update(_expand_range(int(m.group(1)), int(m.group(2))))
        return " "

    rest = _RANGE.sub(take_range, text)

    def take_year(m: re.Match) -> str:
        years.add(int(m.group(1)))
        return " "

    rest = _YEAR.sub(take_year, rest)

    radius = _RADIUS.search(rest)
    if radius:
        out.radius_km = float(radius.group(1))
        rest = _RADIUS.sub(" ", rest)

    out.future_years = sorted(y for y in years if y > this_year)
    out.years = sorted(y for y in years if y <= this_year)

    # Drop "?" "!" ":" ";" and quotes; keep commas, hyphens, apostrophes and periods.
    rest = re.sub(r"[?!:;\"“”()]", " ", rest)
    tokens = [t for t in rest.split() if re.search(r"\w", t)]

    def bare(tok: str) -> str:
        return re.sub(r"(?:'s|’s)$", "", tok.strip(",.").lower())

    while tokens and bare(tokens[0]) in _STOP:
        tokens.pop(0)
    while tokens and bare(tokens[-1]) in _STOP:
        tokens.pop()

    place = " ".join(tokens).strip(" ,.")
    place = re.sub(r"(?:'s|’s)$", "", place)
    out.place = place
    return out
