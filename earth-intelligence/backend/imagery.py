"""Historical imagery + land-cover retrieval from Google Earth Engine.

For each requested year we produce:
  * a Sentinel-2 true-colour median composite (cloud-masked),
  * a Dynamic World V1 land-cover map (per-pixel mode of the yearly label),
  * land-cover area statistics for the region.

Everything returned is observed historical data. There is no forecasting here.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import ee

from .ee_client import init_ee
from .geocode import geocode

# Dynamic World V1 label values 0-8.
LAND_COVER_CLASSES = [
    ("Water", "419BDF"),
    ("Trees", "397D49"),
    ("Grass", "88B053"),
    ("Flooded vegetation", "7A87C6"),
    ("Crops", "E49635"),
    ("Shrub & scrub", "DFC35A"),
    ("Built-up", "C4281B"),
    ("Bare ground", "A59B8F"),
    ("Snow & ice", "B39FE1"),
]
PALETTE = [c for _, c in LAND_COVER_CLASSES]

MIN_YEAR = 2016  # Dynamic World starts mid-2015; 2016 is the first full year.
MAX_YEARS = 6
THUMB_PX = 768
STATS_SCALE_M = 30  # coarser than native 10 m so stats stay fast on big regions


def _bbox(lat: float, lon: float, radius_km: float) -> list[float]:
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]


def _mask_s2_clouds(img: ee.Image) -> ee.Image:
    qa = img.select("QA60")
    cloud_bit, cirrus_bit = 1 << 10, 1 << 11
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    return img.updateMask(mask)


def _s2_collection(region: ee.Geometry, year: int) -> ee.ImageCollection:
    # Level-1C (TOA) is used on purpose: unlike L2A it exists for every year
    # since 2015, so 2016 and 2025 are rendered the same way.
    return (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterBounds(region)
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
    )


def _process_year(region: ee.Geometry, year: int) -> dict[str, Any]:
    s2_col = _s2_collection(region, year)
    scenes = s2_col.size().getInfo()
    if scenes == 0:
        raise ValueError(f"No usable Sentinel-2 scenes found for {year}.")

    s2 = s2_col.map(_mask_s2_clouds).median().clip(region)
    satellite_url = s2.getThumbURL(
        {
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "gamma": 1.2,
            "region": region,
            "dimensions": THUMB_PX,
            "format": "jpg",
        }
    )

    label = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(region)
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01")
        .select("label")
        .mode()
        .clip(region)
    )
    landcover_url = label.getThumbURL(
        {
            "min": 0,
            "max": 8,
            "palette": PALETTE,
            "region": region,
            "dimensions": THUMB_PX,
            "format": "png",
        }
    )

    area_img = ee.Image.pixelArea().addBands(label.rename("label"))
    grouped = area_img.reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="label"),
        geometry=region,
        scale=STATS_SCALE_M,
        maxPixels=1_000_000_000,
        bestEffort=True,
    ).get("groups")
    groups = ee.List(grouped).getInfo() or []

    by_id = {int(g["label"]): float(g["sum"]) / 1e6 for g in groups}  # m2 -> km2
    total = sum(by_id.values()) or 1.0
    stats = [
        {
            "class_id": i,
            "name": name,
            "color": f"#{color}",
            "area_km2": round(by_id.get(i, 0.0), 3),
            "percent": round(100 * by_id.get(i, 0.0) / total, 2),
        }
        for i, (name, color) in enumerate(LAND_COVER_CLASSES)
    ]
    return {
        "year": year,
        "scenes": scenes,
        "satellite_url": satellite_url,
        "landcover_url": landcover_url,
        "total_km2": round(total, 2),
        "stats": stats,
    }


def get_historical_imagery(
    place: str, years: list[int], radius_km: float = 15.0
) -> dict[str, Any]:
    """Fetch composites, land-cover maps and statistics for a place and years."""
    this_year = date.today().year
    years = sorted({int(y) for y in years})
    if not years:
        raise ValueError("Provide at least one year.")
    if len(years) > MAX_YEARS:
        raise ValueError(f"Please request at most {MAX_YEARS} years at a time.")
    for y in years:
        if y < MIN_YEAR or y > this_year:
            raise ValueError(f"Year {y} is outside the supported range {MIN_YEAR}-{this_year}.")
    radius_km = min(max(float(radius_km), 1.0), 40.0)

    init_ee()
    loc = geocode(place)
    region = ee.Geometry.Rectangle(_bbox(loc.lat, loc.lon, radius_km))

    errors: dict[int, str] = {}

    def run(y: int) -> dict[str, Any] | None:
        try:
            return _process_year(region, y)
        except Exception as exc:  # keep other years even if one fails
            errors[y] = str(exc)
            return None

    with ThreadPoolExecutor(max_workers=len(years)) as pool:
        results = [r for r in pool.map(run, years) if r is not None]

    if not results:
        raise RuntimeError("No imagery could be retrieved: " + "; ".join(errors.values()))

    return {
        "place": loc.name,
        "query": place,
        "lat": loc.lat,
        "lon": loc.lon,
        "radius_km": radius_km,
        "years": results,
        "errors": {str(k): v for k, v in errors.items()},
    }


def summarize_for_llm(data: dict[str, Any]) -> dict[str, Any]:
    """Compact, URL-free summary that Gemini can reason over."""
    years = data["years"]
    summary: dict[str, Any] = {
        "place": data["place"],
        "radius_km": data["radius_km"],
        "land_cover_percent_by_year": {
            str(y["year"]): {s["name"]: s["percent"] for s in y["stats"] if s["percent"] > 0}
            for y in years
        },
        "failed_years": data["errors"],
    }
    if len(years) >= 2:
        first, last = years[0], years[-1]
        first_pct = {s["name"]: s["percent"] for s in first["stats"]}
        summary["change_in_percentage_points"] = {
            "from": first["year"],
            "to": last["year"],
            "by_class": {
                s["name"]: round(s["percent"] - first_pct[s["name"]], 2)
                for s in last["stats"]
            },
        }
    return summary
