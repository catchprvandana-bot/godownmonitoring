"""Rule-based spoilage risk scoring.

Thresholds are set for warehouse-stored paddy and pulses (common Tamil Nadu
godown stock), not general produce. Rationale (expand in the pitch narration —
this is Person C's domain-validation contribution):

- Humidity > 70%: paddy grain re-absorbs ambient moisture above this point,
  pushing internal grain moisture past the ~14% safe-storage threshold and
  enabling Aspergillus/Penicillium mold growth within days.
- Temperature > 32C: accelerates both fungal metabolism and insect activity
  (rice weevil, pulse beetle) - infestations that are otherwise dormant at
  cooler storage temps become active breeding populations.
- Gas (CO2 proxy) > 700ppm: elevated CO2 in an enclosed storage zone indicates
  active respiration from mold or insect metabolism - grain itself has very
  low baseline respiration, so a spike is a leading indicator, not a lagging one.

These are placeholder-but-defensible numbers for a hackathon demo. Replace with
crop-specific values (paddy vs. pulses differ) if time allows.
"""

CV_RISK_WEIGHT = {
    "healthy": 0,
    "discoloration": 15,
    "pest_damage": 25,
    "mold": 75,
}

UNCERTAIN_LABEL = "uncertain"
CONFIDENCE_THRESHOLD = 0.60


def score_sensor(sensor: dict) -> tuple[int, list[str]]:
    risk = 0
    reasons = []

    if sensor["humidity_pct"] > 75:
        risk += 40
        reasons.append(f"humidity {sensor['humidity_pct']}% > 75% (high mold risk)")
    elif sensor["humidity_pct"] > 70:
        risk += 20
        reasons.append(f"humidity {sensor['humidity_pct']}% > 70% (elevated)")

    if sensor["temperature_c"] > 32:
        risk += 30
        reasons.append(f"temperature {sensor['temperature_c']}C > 32C (pest/mold accelerant)")
    elif sensor["temperature_c"] > 30:
        risk += 15
        reasons.append(f"temperature {sensor['temperature_c']}C > 30C (elevated)")

    if sensor["gas_ppm"] > 700:
        risk += 30
        reasons.append(f"gas {sensor['gas_ppm']}ppm > 700ppm (active respiration/spoilage signal)")
    elif sensor["gas_ppm"] > 550:
        risk += 15
        reasons.append(f"gas {sensor['gas_ppm']}ppm > 550ppm (elevated)")

    return min(risk, 100), reasons


def combine_with_vision(sensor_risk: int, cv_label: str | None, cv_confidence: float | None) -> tuple[int, list[str]]:
    """Blend the sensor-only score with the latest CV classification for a zone, if any."""
    reasons: list[str] = []
    if cv_label is None:
        return sensor_risk, reasons

    if cv_confidence is not None and cv_confidence < CONFIDENCE_THRESHOLD:
        reasons.append(
            f"vision result '{cv_label}' below {int(CONFIDENCE_THRESHOLD * 100)}% confidence -> flagged for manual check"
        )
        return min(sensor_risk + 10, 100), reasons

    cv_add = CV_RISK_WEIGHT.get(cv_label, 0)
    if cv_add:
        reasons.append(f"vision classified '{cv_label}' (+{cv_add})")
    return min(sensor_risk + cv_add, 100), reasons


def risk_level(score: int) -> str:
    if score >= 70:
        return "red"
    if score >= 40:
        return "yellow"
    return "green"
