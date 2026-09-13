"""
Cost calculation and economic analysis endpoints for real-time avatar streaming.
Implements the cost assumptions and estimation engine required by Assignment 02.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict, Any

router = APIRouter(prefix="/api/v1", tags=["Economics & Costs"])

PROVIDER_COSTS_PER_MINUTE = {
    "edge-tts": {
        "provider_name": "Lightweight 2D Neural Canvas (Edge-TTS)",
        "cost_per_minute_usd": 0.00008,  # ~$0.005 / hour compute only
        "video_cost_per_minute_usd": 0.0,
        "tts_cost_per_minute_usd": 0.0,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 32,
        "tier": "Free / Self-Hosted",
        "description": "Zero external API fees. Client-side canvas + unmetered 24kHz HD neural speech."
    },
    "simli": {
        "provider_name": "Simli Ultra-Low Latency WebRTC",
        "cost_per_minute_usd": 0.02,
        "video_cost_per_minute_usd": 0.02,
        "tts_cost_per_minute_usd": 0.00,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 600,
        "tier": "Developer / Growth",
        "description": "Sub-300ms audio-to-video neural rendering. Free dev minutes included."
    },
    "anam": {
        "provider_name": "Anam.ai Conversational Digital Human",
        "cost_per_minute_usd": 0.03,
        "video_cost_per_minute_usd": 0.03,
        "tts_cost_per_minute_usd": 0.00,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 750,
        "tier": "Free Starter / Growth",
        "description": "Next-gen ultra-realistic conversational human with native WebRTC data channels."
    },
    "akool": {
        "provider_name": "Akool Streaming Avatar",
        "cost_per_minute_usd": 0.04,
        "video_cost_per_minute_usd": 0.04,
        "tts_cost_per_minute_usd": 0.00,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 800,
        "tier": "Trial Credits / Pro",
        "description": "High-fidelity real-time streaming avatar with lip-sync."
    },
    "heygen": {
        "provider_name": "HeyGen Streaming & Studio Video",
        "cost_per_minute_usd": 0.08,
        "video_cost_per_minute_usd": 0.08,
        "tts_cost_per_minute_usd": 0.00,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 1200,
        "tier": "Paid / Enterprise",
        "description": "Studio-grade digital avatars with interactive streaming."
    },
    "d-id": {
        "provider_name": "D-ID Real-Time WebRTC Video",
        "cost_per_minute_usd": 0.10,
        "video_cost_per_minute_usd": 0.10,
        "tts_cost_per_minute_usd": 0.00,
        "compute_cost_per_minute_usd": 0.00008,
        "bandwidth_kb_per_sec": 1000,
        "tier": "Trial (20 credits) / Pro",
        "description": "Photorealistic live video stream with talking-head motion."
    }
}


class CostEstimateRequest(BaseModel):
    sessions_per_month: int = Field(default=1000, description="Estimated total sessions per month")
    avg_duration_minutes: float = Field(default=2.5, description="Average duration of each session in minutes")
    active_engine: str = Field(default="edge-tts", description="Avatar engine to benchmark")


class CostEstimateResponse(BaseModel):
    sessions_per_month: int
    avg_duration_minutes: float
    total_streaming_minutes: float
    selected_engine_cost_usd: float
    comparison_breakdown: Dict[str, Any]
    summary_recommendation: str


@router.get(
    "/costs",
    summary="Get Running Cost Assumptions & Engine Pricing Models",
    description="Returns cost assumptions per minute, bandwidth requirements, and unit economics across all supported engines."
)
async def get_cost_assumptions():
    return {
        "currency": "USD",
        "unit": "per_streaming_minute",
        "providers": PROVIDER_COSTS_PER_MINUTE,
        "monthly_projection_presets": {
            "startup_1k_users": {
                "monthly_sessions": 1000,
                "avg_session_min": 2.0,
                "total_minutes": 2000,
                "costs": {k: round(v["cost_per_minute_usd"] * 2000, 2) for k, v in PROVIDER_COSTS_PER_MINUTE.items()}
            },
            "growth_10k_users": {
                "monthly_sessions": 10000,
                "avg_session_min": 2.5,
                "total_minutes": 25000,
                "costs": {k: round(v["cost_per_minute_usd"] * 25000, 2) for k, v in PROVIDER_COSTS_PER_MINUTE.items()}
            },
            "scale_100k_users": {
                "monthly_sessions": 100000,
                "avg_session_min": 3.0,
                "total_minutes": 300000,
                "costs": {k: round(v["cost_per_minute_usd"] * 300000, 2) for k, v in PROVIDER_COSTS_PER_MINUTE.items()}
            }
        }
    }


@router.post(
    "/costs/estimate",
    response_model=CostEstimateResponse,
    summary="Calculate Projected Monthly Running Cost",
    description="Calculates projected infrastructure and API costs for custom session volumes and duration."
)
async def estimate_costs(request: CostEstimateRequest):
    total_mins = request.sessions_per_month * request.avg_duration_minutes
    breakdown = {}

    for engine, spec in PROVIDER_COSTS_PER_MINUTE.items():
        total_cost = round(spec["cost_per_minute_usd"] * total_mins, 2)
        bandwidth_gb = round((spec["bandwidth_kb_per_sec"] * 60 * total_mins) / (1024 * 1024), 2)
        breakdown[engine] = {
            "name": spec["provider_name"],
            "total_cost_usd": total_cost,
            "cost_per_session_usd": round(total_cost / max(1, request.sessions_per_month), 4),
            "estimated_bandwidth_gb": bandwidth_gb,
            "tier": spec["tier"]
        }

    active_spec = PROVIDER_COSTS_PER_MINUTE.get(request.active_engine, PROVIDER_COSTS_PER_MINUTE["edge-tts"])
    selected_cost = round(active_spec["cost_per_minute_usd"] * total_mins, 2)

    return CostEstimateResponse(
        sessions_per_month=request.sessions_per_month,
        avg_duration_minutes=request.avg_duration_minutes,
        total_streaming_minutes=total_mins,
        selected_engine_cost_usd=selected_cost,
        comparison_breakdown=breakdown,
        summary_recommendation="For high-volume cost efficiency, deploy the Lightweight 2D Canvas Engine ($0 API fees). For high-touch sales, switch to D-ID or Anam.ai WebRTC."
    )
