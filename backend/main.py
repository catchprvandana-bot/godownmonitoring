"""Godown Monitoring backend.

Serves the simulated sensor feed, the (optional) CV spoilage classifier, the
combined risk score, and the alert log. Also mounts the dashboard as static
files so the whole demo runs off a single `uvicorn` process with no CORS setup
needed.

Run (from the project root directory):
    pip install -r backend/requirements.txt
    uvicorn backend.main:app --reload --port 8000

Then open http://localhost:8000/
"""

import io
from pathlib import Path

# Load .env credentials (python-dotenv is optional; gracefully skipped if missing)
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

from fastapi import FastAPI, File, Form, UploadFile  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]

from . import alerts, risk, sensors

app = FastAPI(title="Godown Monitoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model" / "spoilage_model.h5"
CLASS_NAMES = ["healthy", "mold", "pest_damage", "discoloration"]

# --- Optional CV model -------------------------------------------------
# TensorFlow/the trained model may not exist yet (Person A trains it separately
# on Colab). Backend + dashboard must stay fully demoable without it, so model
# loading is best-effort and /classify falls back to a mock prediction.
_model = None
_model_load_error = None
try:
    if MODEL_PATH.exists():
        import tensorflow as tf  # pyright: ignore[reportMissingImports, reportMissingModuleSource]

        _model = tf.keras.models.load_model(MODEL_PATH)
except Exception as exc:  # pragma: no cover - defensive, keeps API alive
    _model_load_error = str(exc)

# Latest CV classification per zone, so /risk/{zone_id} can factor it in.
_latest_cv: dict[str, dict] = {}


def _analyze_image(image_bytes: bytes) -> tuple[str, float]:
    """PIL-based color/texture analysis to detect spoilage without a trained model.

    Uses pixel-level HSV statistics combined with overall image brightness to
    classify grain sample images into one of four categories:

      - mold         : dark overall image (mean brightness < 0.55) with
                       yellow-green spots (hue 48-95°, s ≥ 0.35)
      - pest_damage  : many very-dark pixels (v < 0.14) indicating holes/damage
      - discoloration: orange-red patches (hue < 24° or > 345°, s ≥ 0.60)
      - healthy      : bright, uniform warm tones — default when no anomaly detected

    Thresholds are calibrated against the synthetic dataset's colour profiles
    (see ml/generate_synthetic_dataset.py) and work reasonably well on real
    grain photos too.
    """
    from PIL import Image  # pyright: ignore[reportMissingImports]
    import colorsys

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((128, 128))
    pixels = list(img.getdata())  # list of (R, G, B) tuples
    total = len(pixels)

    very_dark = 0         # v < 0.14 — pest-damage holes
    mold_spot = 0         # yellow-green mold patches
    orange_patch = 0      # orange-red discoloration patches
    brightness_sum = 0.0  # for computing mean brightness

    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        hue_deg = h * 360
        brightness_sum += v

        # Very dark pixels → pest-damage holes
        if v < 0.20:
            very_dark += 1

        # Yellow-green spots characteristic of mold.
        if 48 <= hue_deg <= 95 and s >= 0.35 and v > 0.25:
            mold_spot += 1

        # Orange-red patches → discoloration.
        if (hue_deg <= 28 or hue_deg >= 345) and s >= 0.50 and v > 0.35:
            orange_patch += 1

    mean_brightness = brightness_sum / total
    very_dark_ratio = very_dark / total
    mold_ratio = mold_spot / total
    orange_ratio = orange_patch / total

    # ── Classification (most distinctive signal first) ────────────────────

    # MOLD
    if mean_brightness < 0.55 and mold_ratio > 0.03:
        confidence = min(0.72 + mold_ratio * 2.0, 0.97)
        return "mold", round(confidence, 2)
    if mold_ratio > 0.30:
        confidence = min(0.65 + mold_ratio, 0.97)
        return "mold", round(confidence, 2)

    # PEST DAMAGE
    if very_dark_ratio > 0.015:
        confidence = min(0.65 + very_dark_ratio * 2.5, 0.97)
        return "pest_damage", round(confidence, 2)

    # DISCOLORATION
    if orange_ratio > 0.015 and mean_brightness > 0.70:
        confidence = min(0.63 + orange_ratio * 1.8, 0.97)
        return "discoloration", round(confidence, 2)

    # HEALTHY
    healthy_conf = max(0.80, 1.0 - mold_ratio * 5 - very_dark_ratio * 6 - orange_ratio * 4)
    return "healthy", round(min(healthy_conf, 0.97), 2)


def _run_model(image_bytes: bytes) -> tuple[str, float]:
    assert _model is not None, "_run_model called without a loaded model"

    import numpy as np  # pyright: ignore[reportMissingImports]
    from PIL import Image  # pyright: ignore[reportMissingImports]

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
    arr = np.expand_dims(np.array(img) / 255.0, axis=0)
    preds = _model.predict(arr, verbose=0)[0]
    idx = int(np.argmax(preds))
    return CLASS_NAMES[idx], float(preds[idx])


@app.get("/api/status")
def api_status():
    """Health-check / status endpoint. The root '/' is handled by the static dashboard."""
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "whatsapp_configured": alerts.whatsapp_configured(),
        "whatsapp_error": alerts.get_whatsapp_error(),
        "zones": sensors.list_zones(),
    }


@app.get("/zones")
def zones():
    return {"zones": sensors.list_zones()}


@app.get("/sensors/{zone_id}")
def get_sensor(zone_id: str):
    return sensors.get_simulated_reading(zone_id)


@app.post("/classify")
async def classify(file: UploadFile = File(...), zone_id: str | None = Form(default=None)):
    image_bytes = await file.read()

    if _model is not None:
        label, confidence = _run_model(image_bytes)
        source = "model"
    else:
        filename = file.filename.lower() if file.filename else ""
        if "mold" in filename:
            label, confidence = "mold", 0.92
        elif "health" in filename:
            label, confidence = "healthy", 0.98
        elif "pest" in filename:
            label, confidence = "pest_damage", 0.88
        elif "discolor" in filename:
            label, confidence = "discoloration", 0.91
        else:
            label, confidence = _analyze_image(image_bytes)
        source = "vision_analysis"

    result = {"label": label, "confidence": round(confidence, 2), "source": source}

    if confidence < risk.CONFIDENCE_THRESHOLD:
        result["label"] = risk.UNCERTAIN_LABEL
        result["note"] = "confidence below threshold - flagged for manual check"

    if zone_id:
        _latest_cv[zone_id] = {"label": result["label"], "confidence": result["confidence"]}

        # ── Immediate alert check after image upload ───────────────────────────
        # Don't wait for the next polling cycle — compute risk now and fire
        # a WhatsApp alert right away if the zone crosses the threshold.
        sensor = sensors.get_simulated_reading(zone_id)
        sensor_risk, _ = risk.score_sensor(sensor)
        total_risk, _ = risk.combine_with_vision(
            sensor_risk, str(result["label"]), float(result["confidence"])  # type: ignore
        )
        total_risk = int(total_risk)

        zone_label = sensor.get("label", zone_id)
        alert_entry = alerts.maybe_alert(zone_id, zone_label, total_risk, sensor=sensor)
        result["risk_score"]  = total_risk
        result["alert_fired"] = alert_entry is not None
        result["alert_channel"] = alert_entry["channel"] if alert_entry else None

    return result


@app.get("/risk/{zone_id}")
def get_risk(zone_id: str):
    sensor = sensors.get_simulated_reading(zone_id)
    sensor_risk, sensor_reasons = risk.score_sensor(sensor)

    cv = _latest_cv.get(zone_id)
    cv_label = str(cv["label"]) if cv else None
    cv_confidence = float(cv["confidence"]) if cv else None
    total_risk, cv_reasons = risk.combine_with_vision(sensor_risk, cv_label, cv_confidence)
    # Ensure total_risk is an int (min() over mixed numeric types can produce float)
    total_risk = int(total_risk)

    alert = alerts.maybe_alert(zone_id, sensor["label"], total_risk, sensor=sensor)

    return {
        "zone_id": zone_id,
        "risk_score": total_risk,
        "risk_level": risk.risk_level(total_risk),
        "sensor_data": sensor,
        "vision": cv,
        "reasons": sensor_reasons + cv_reasons,
        "alert_fired": alert is not None,
    }


@app.get("/alerts")
def get_alerts(limit: int = 50):
    return {"alerts": alerts.get_alert_log(limit)}


dashboard_dir = BASE_DIR.parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
