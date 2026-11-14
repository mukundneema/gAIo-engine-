"""Gemini chat with function calling into our Earth Engine retrieval code."""
from __future__ import annotations

import os
from typing import Any

from google import genai
from google.genai import types

from .imagery import MAX_YEARS, MIN_YEAR, get_historical_imagery, summarize_for_llm

SYSTEM_PROMPT = f"""You are Earth Intelligence, an assistant that explains how places on Earth \
have changed, using real satellite data from Google Earth Engine (Sentinel-2 imagery and \
Dynamic World land-cover classification).

Rules:
- When the user asks to see a place in particular years, call get_historical_imagery. \
Supported years are {MIN_YEAR} to the present, at most {MAX_YEARS} per request.
- The images and statistics are shown to the user automatically in the interface. Do not \
describe image URLs. Summarise what the numbers show (e.g. built-up area growth) in a few \
concise sentences.
- Only report figures that come from tool results. Never invent statistics.
- Forecasting is NOT available yet. If asked about the future, say that the platform \
currently covers observed history only, and never fabricate future imagery or numbers. \
You may offer to show the historical trend instead.
- Land cover percentages come from a 30 m resolution sampling of a square region around \
the place centre; mention the radius when it matters.
"""

_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_historical_imagery",
            description=(
                "Retrieve Sentinel-2 satellite composites, Dynamic World land-cover maps and "
                "land-cover area statistics for a place in one or more past years."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "place": types.Schema(
                        type=types.Type.STRING,
                        description="Place name, e.g. 'Mumbai, India'.",
                    ),
                    "years": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.INTEGER),
                        description="Calendar years to retrieve, e.g. [2016, 2020, 2025].",
                    ),
                    "radius_km": types.Schema(
                        type=types.Type.NUMBER,
                        description="Half-width of the square area around the place in km. Default 15.",
                    ),
                },
                required=["place", "years"],
            ),
        )
    ]
)


def _client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    return genai.Client(api_key=key)


def _history_to_contents(messages: list[dict[str, str]]) -> list[types.Content]:
    contents: list[types.Content] = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    return contents


def chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Run one chat turn. Returns {'reply': str, 'results': [imagery results]}."""
    client = _client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_TOOL],
        # We run the tool loop ourselves so we can pass the full imagery payload
        # (image URLs etc.) to the frontend while Gemini only sees a summary.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents = _history_to_contents(messages)
    results: list[dict[str, Any]] = []

    for _ in range(4):  # bounded tool loop
        response = client.models.generate_content(model=model, contents=contents, config=config)
        calls = response.function_calls or []
        if not calls:
            return {"reply": response.text or "", "results": results}

        contents.append(response.candidates[0].content)
        response_parts: list[types.Part] = []
        for call in calls:
            args = dict(call.args or {})
            try:
                if call.name != "get_historical_imagery":
                    raise ValueError(f"Unknown function {call.name}")
                data = get_historical_imagery(
                    place=str(args["place"]),
                    years=[int(y) for y in args["years"]],
                    radius_km=float(args.get("radius_km", 15.0)),
                )
                results.append(data)
                payload: dict[str, Any] = {"result": summarize_for_llm(data)}
            except Exception as exc:
                payload = {"error": str(exc)}
            response_parts.append(
                types.Part.from_function_response(name=call.name, response=payload)
            )
        contents.append(types.Content(role="user", parts=response_parts))

    return {
        "reply": "I retrieved the data but ran out of steps writing the summary. "
        "The imagery and statistics are shown above.",
        "results": results,
    }
