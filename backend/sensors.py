"""Simulated sensor feed.

Real hardware (DHT22 temp/humidity, MQ-series gas sensors) is out of scope for the
36-hour build. Instead of pure random noise per request, each zone keeps a small
in-memory state that drifts over time (a random walk around a per-zone baseline).
One zone is seeded as a "bad zone" that trends upward toward spoilage-risk
territory, so a live demo can show an escalating story instead of static numbers.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ZoneConfig:
    label: str
    temp: float
    humidity: float
    gas: float
    trend: float  # nudges the random walk each call; >0 trends toward spoilage risk


# Per-zone baseline + drift configuration. zone-c is seeded as the "bad zone"
# (trend > 0) so a demo run shows an escalating risk story, not just noise.
ZONE_CONFIG: dict[str, ZoneConfig] = {
    "zone-a": ZoneConfig(label="Paddy Store A", temp=27.0, humidity=62.0, gas=420.0, trend=0.0),
    "zone-b": ZoneConfig(label="Pulses Store B", temp=28.0, humidity=65.0, gas=450.0, trend=0.0),
    "zone-c": ZoneConfig(label="Paddy Store C (leaky roof)", temp=30.5, humidity=73.5, gas=570.0, trend=1.5),
}

# Bounds so the random walk doesn't drift into nonsense values.
BOUNDS: dict[str, tuple[float, float]] = {
    "temp": (20.0, 40.0),
    "humidity": (40.0, 95.0),
    "gas": (250.0, 950.0),
}

_state: dict[str, dict[str, float]] = {
    zone_id: {"temp": cfg.temp, "humidity": cfg.humidity, "gas": cfg.gas}
    for zone_id, cfg in ZONE_CONFIG.items()
}


def _clamp(value: float, key: str) -> float:
    lo, hi = BOUNDS[key]
    return max(lo, min(hi, value))


def _step(zone_id: str) -> dict[str, float]:
    cfg = ZONE_CONFIG[zone_id]
    state = _state[zone_id]

    # Small random walk + a steady trend for zones simulating a real problem (e.g. a leak).
    state["temp"] = _clamp(state["temp"] + random.uniform(-0.4, 0.4), "temp")
    state["humidity"] = _clamp(
        state["humidity"] + random.uniform(-0.6, 0.6) + cfg.trend * 0.3, "humidity"
    )
    state["gas"] = _clamp(state["gas"] + random.uniform(-15, 15) + cfg.trend * 8, "gas")
    return state


def list_zones() -> list[str]:
    return list(ZONE_CONFIG.keys())


def get_simulated_reading(zone_id: str) -> dict:
    if zone_id not in ZONE_CONFIG:
        # Unknown zones still get a plausible reading instead of erroring the demo.
        ZONE_CONFIG[zone_id] = ZoneConfig(label=zone_id, temp=28.0, humidity=65.0, gas=450.0, trend=0.0)
        _state[zone_id] = {"temp": 28.0, "humidity": 65.0, "gas": 450.0}

    state = _step(zone_id)
    return {
        "zone_id": zone_id,
        "label": ZONE_CONFIG[zone_id].label,
        "temperature_c": round(state["temp"], 1),
        "humidity_pct": round(state["humidity"], 1),
        "gas_ppm": round(state["gas"], 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
