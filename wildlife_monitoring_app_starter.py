from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import date, timedelta
import math

app = FastAPI(title="Wildlife Monitoring App Starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PURPOSE
# -------------------------------------------------------------------
# This starter app is for lawful wildlife monitoring, habitat analysis,
# land management, conservation, and recovery planning.
#
# It does NOT identify live animal positions for hunting.
# Instead, it scores likely grazing / resting habitat based on:
# - vegetation quality (NDVI-like input)
# - distance to water
# - land-cover suitability
# - slope / terrain openness
# - optional historical sightings collected by the landowner/rangers
# -------------------------------------------------------------------

class AOI(BaseModel):
    name: str = Field(..., description="Area name")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[min_lon, min_lat, max_lon, max_lat]",
    )


class SpeciesWeights(BaseModel):
    species: Literal["springbok", "blesbok", "wildebeest", "kudu", "oryx", "generic_grazer"]
    vegetation_weight: float = 0.4
    water_weight: float = 0.25
    openness_weight: float = 0.2
    slope_weight: float = 0.1
    sightings_weight: float = 0.05


class HabitatCell(BaseModel):
    lat: float
    lon: float
    ndvi: float = Field(..., ge=-1.0, le=1.0)
    distance_to_water_m: float = Field(..., ge=0)
    openness: float = Field(..., ge=0.0, le=1.0)
    slope_deg: float = Field(..., ge=0.0, le=90.0)
    historical_sightings_30d: int = Field(0, ge=0)


class HabitatScoreRequest(BaseModel):
    aoi: AOI
    species_weights: SpeciesWeights
    cells: List[HabitatCell]
    observation_date: Optional[date] = None


class HabitatScoreResult(BaseModel):
    lat: float
    lon: float
    habitat_score: float
    confidence: float
    label: str


SPECIES_PROFILES = {
    "springbok": {
        "preferred_ndvi": (0.18, 0.48),
        "max_water_distance_m": 8000,
        "preferred_openness": 0.75,
        "max_slope_deg": 12,
    },
    "blesbok": {
        "preferred_ndvi": (0.25, 0.6),
        "max_water_distance_m": 6000,
        "preferred_openness": 0.8,
        "max_slope_deg": 10,
    },
    "wildebeest": {
        "preferred_ndvi": (0.22, 0.55),
        "max_water_distance_m": 7000,
        "preferred_openness": 0.7,
        "max_slope_deg": 14,
    },
    "kudu": {
        "preferred_ndvi": (0.2, 0.5),
        "max_water_distance_m": 9000,
        "preferred_openness": 0.45,
        "max_slope_deg": 18,
    },
    "oryx": {
        "preferred_ndvi": (0.1, 0.35),
        "max_water_distance_m": 12000,
        "preferred_openness": 0.8,
        "max_slope_deg": 16,
    },
    "generic_grazer": {
        "preferred_ndvi": (0.2, 0.5),
        "max_water_distance_m": 8000,
        "preferred_openness": 0.7,
        "max_slope_deg": 15,
    },
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def score_ndvi(ndvi: float, low: float, high: float) -> float:
    if low <= ndvi <= high:
        return 1.0
    if ndvi < low:
        return clamp(1 - ((low - ndvi) / 0.25), 0.0, 1.0)
    return clamp(1 - ((ndvi - high) / 0.25), 0.0, 1.0)


def score_water(distance_to_water_m: float, max_distance: float) -> float:
    if distance_to_water_m >= max_distance:
        return 0.0
    return clamp(1 - (distance_to_water_m / max_distance), 0.0, 1.0)


def score_openness(openness: float, preferred: float) -> float:
    return clamp(1 - abs(openness - preferred) / 0.6, 0.0, 1.0)


def score_slope(slope_deg: float, max_slope: float) -> float:
    if slope_deg <= max_slope:
        return 1.0
    return clamp(1 - ((slope_deg - max_slope) / 25.0), 0.0, 1.0)


def score_sightings(historical_sightings_30d: int) -> float:
    return clamp(historical_sightings_30d / 12.0, 0.0, 1.0)


def label_score(score: float) -> str:
    if score >= 0.8:
        return "very_high"
    if score >= 0.6:
        return "high"
    if score >= 0.4:
        return "medium"
    if score >= 0.2:
        return "low"
    return "very_low"


@app.get("/")
def root():
    return {"message": "Wildlife Monitoring API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"ok": True, "service": "wildlife_monitoring_app_starter"}


@app.post("/score-habitat", response_model=List[HabitatScoreResult])
def score_habitat(payload: HabitatScoreRequest):
    profile = SPECIES_PROFILES.get(payload.species_weights.species)
    if not profile:
        raise HTTPException(status_code=400, detail="Unknown species")

    results = []
    for cell in payload.cells:
        ndvi_component = score_ndvi(cell.ndvi, profile["preferred_ndvi"][0], profile["preferred_ndvi"][1])
        water_component = score_water(cell.distance_to_water_m, profile["max_water_distance_m"])
        openness_component = score_openness(cell.openness, profile["preferred_openness"])
        slope_component = score_slope(cell.slope_deg, profile["max_slope_deg"])
        sightings_component = score_sightings(cell.historical_sightings_30d)

        raw_score = (
            ndvi_component * payload.species_weights.vegetation_weight
            + water_component * payload.species_weights.water_weight
            + openness_component * payload.species_weights.openness_weight
            + slope_component * payload.species_weights.slope_weight
            + sightings_component * payload.species_weights.sightings_weight
        )

        agreement = sum([
            1 if ndvi_component > 0.6 else 0,
            1 if water_component > 0.6 else 0,
            1 if openness_component > 0.6 else 0,
            1 if slope_component > 0.6 else 0,
        ]) / 4.0
        confidence = clamp((0.65 * agreement) + (0.35 * sightings_component), 0.1, 0.99)

        results.append(
            HabitatScoreResult(
                lat=cell.lat,
                lon=cell.lon,
                habitat_score=round(raw_score, 4),
                confidence=round(confidence, 4),
                label=label_score(raw_score),
            )
        )

    results.sort(key=lambda r: r.habitat_score, reverse=True)
    return results


@app.get("/demo-request")
def demo_request():
    return {
        "aoi": {"name": "Demo Farm", "bbox": [24.1, -28.9, 24.3, -28.7]},
        "species_weights": {
            "species": "springbok",
            "vegetation_weight": 0.4,
            "water_weight": 0.25,
            "openness_weight": 0.2,
            "slope_weight": 0.1,
            "sightings_weight": 0.05,
        },
        "cells": [
            {
                "lat": -28.81,
                "lon": 24.19,
                "ndvi": 0.31,
                "distance_to_water_m": 1800,
                "openness": 0.84,
                "slope_deg": 4,
                "historical_sightings_30d": 8,
            },
            {
                "lat": -28.80,
                "lon": 24.22,
                "ndvi": 0.12,
                "distance_to_water_m": 9500,
                "openness": 0.76,
                "slope_deg": 3,
                "historical_sightings_30d": 1,
            },
            {
                "lat": -28.79,
                "lon": 24.27,
                "ndvi": 0.22,
                "distance_to_water_m": 5400,
                "openness": 0.65,
                "slope_deg": 8,
                "historical_sightings_30d": 4,
            },
        ],
    }
