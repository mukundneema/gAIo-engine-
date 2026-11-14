"""AI-free chat: parse the request, fetch real data, write a templated summary.

Used automatically when GEMINI_API_KEY is not set. Everything it reports comes
straight from the Earth Engine results; nothing is generated or guessed.
"""
from __future__ import annotations

from typing import Any

from .parse_request import ParsedRequest, parse_request

HELP = (
    "Tell me a place and the years to compare, for example:\n"
    "• Show me Mumbai in 2016, 2020, and 2025\n"
    "• Las Vegas 2018-2025\n"
    "• Dubai 2017 and 2024 within 20 km"
)

FORECAST_MSG = (
    "Forecasting isn't available yet. This tool only shows observed history "
    "(2016 to now). I can show you how the place has changed so far if you tell me "
    "the past years you want to compare."
)


def _fmt_pp(x: float) -> str:
    return f"{x:+.1f} points"


def describe(data: dict[str, Any]) -> str:
    years = data["years"]
    lines = [f"Here is {data['place'].split(',')[0]} across {', '.join(str(y['year']) for y in years)} "
             f"(a {data['radius_km']:g} km radius around the centre)."]

    if len(years) >= 2:
        first, last = years[0], years[-1]
        fp = {s["name"]: s["percent"] for s in first["stats"]}
        changes = sorted(
            ((s["name"], s["percent"] - fp[s["name"]], fp[s["name"]], s["percent"]) for s in last["stats"]),
            key=lambda c: abs(c[1]),
            reverse=True,
        )
        notable = [c for c in changes if abs(c[1]) >= 0.5][:3]
        if notable:
            parts = [
                f"{name} went from {a:.1f}% to {b:.1f}% ({_fmt_pp(d)})"
                for name, d, a, b in notable
            ]
            lines.append(f"Biggest changes {first['year']} to {last['year']}: " + "; ".join(parts) + ".")
        else:
            lines.append(
                f"Land-cover shares changed by less than half a percentage point between "
                f"{first['year']} and {last['year']}."
            )
    else:
        top = sorted(years[0]["stats"], key=lambda s: s["percent"], reverse=True)[:3]
        lines.append(
            f"In {years[0]['year']} the largest land covers were "
            + ", ".join(f"{s['name']} ({s['percent']:.1f}%)" for s in top)
            + "."
        )

    if data["errors"]:
        lines.append("Some years couldn't be retrieved: " + "; ".join(f"{y}: {m}" for y, m in data["errors"].items()))
    lines.append(
        "Percentages are sampled at 30 m from Dynamic World labels, so small differences "
        "can be classification noise rather than real change."
    )
    return " ".join(lines)


def _resolve(messages: list[dict[str, str]]) -> ParsedRequest:
    """Parse the latest user message; reuse an earlier place for follow-ups."""
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    latest = parse_request(user_msgs[-1])
    if not latest.place:
        for earlier in reversed(user_msgs[:-1]):
            prev = parse_request(earlier)
            if prev.place:
                latest.place = prev.place
                if latest.radius_km is None:
                    latest.radius_km = prev.radius_km
                break
    return latest


def chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    from .imagery import MAX_YEARS, MIN_YEAR, get_historical_imagery  # lazy: needs earthengine

    req = _resolve(messages)

    if req.wants_forecast or req.future_years:
        return {"reply": FORECAST_MSG, "results": []}
    if not req.place and not req.years:
        return {"reply": HELP, "results": []}
    if not req.place:
        return {"reply": "Which place do you want to look at?\n\n" + HELP, "results": []}
    if not req.years:
        return {
            "reply": f"Which years should I show for {req.place}? (any from {MIN_YEAR} onward, "
            f"up to {MAX_YEARS} at a time)",
            "results": [],
        }

    try:
        data = get_historical_imagery(req.place, req.years, req.radius_km or 15.0)
    except ValueError as exc:  # bad place / year out of range / too many years
        return {"reply": str(exc), "results": []}

    return {"reply": describe(data), "results": [data]}
