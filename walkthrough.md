# Walkthrough: API Testing Flow

The backend server is currently running successfully on `http://127.0.0.1:8000`. You can see its live output in the background task logs. 

Below is the step-by-step flow I just used to test the full lifecycle of the application: sensor simulation -> CV classification -> risk scoring -> alert dispatching.

---

## 1. Verify System Status
First, check that the API is up, Twilio config is picked up, and all zones are registered.
**Endpoint:** `GET /api/status`
```json
{
  "status": "ok",
  "model_loaded": false,
  "twilio_configured": true,
  "zones": ["zone-a", "zone-b", "zone-c"]
}
```
*(Note: `model_loaded` is false locally because of Python 3.14 restrictions, but it will seamlessly fall back to mock predictions)*

## 2. Check the Live Sensor Feed
Read the current drift state of any zone.
**Endpoint:** `GET /sensors/zone-c`
```json
{
  "zone_id": "zone-c",
  "label": "Paddy Store C (leaky roof)",
  "temperature_c": 28.6,
  "humidity_pct": 67.7,
  "gas_ppm": 474.1,
  "timestamp": "2026-07-30T17:05:35.158157+00:00"
}
```

## 3. Submit a Photo for Spoilage Classification
Upload an image of the grains to update the CV risk factor for that zone.
**Endpoint:** `POST /classify` (Multipart form-data)
```powershell
curl.exe -X POST "http://127.0.0.1:8000/classify" `
  -F "file=@ml/dataset/val/healthy/healthy_0000.jpg" `
  -F "zone_id=zone-c"
```
**Response:**
```json
{
  "label": "uncertain",
  "confidence": 0.56,
  "source": "mock",
  "note": "confidence below threshold - flagged for manual check"
}
```

## 4. Escalate the Risk Score
Because we hardcoded `zone-c` to have a positive "trend" in `sensors.py`, its sensor values slowly escalate towards spoilage conditions every time it is polled. I polled it 30 times in a fast loop to force a critical state:
**Endpoint:** `GET /risk/zone-c`

*Initial calls:*
```json
{"zone_id": "zone-c", "risk_score": 45, "risk_level": "yellow", ...}
```
*After repeated calls (temperature, humidity, and gas spike):*
```json
{
  "zone_id": "zone-c",
  "risk_score": 80,
  "risk_level": "red",
  "sensor_data": {
    "temperature_c": 27.5,
    "humidity_pct": 76.5,
    "gas_ppm": 701.5
  },
  "reasons": [
    "humidity 76.5% > 75% (high mold risk)",
    "gas 701.5ppm > 700ppm (active respiration/spoilage signal)",
    "vision result 'uncertain' below 60% confidence -> flagged for manual check"
  ],
  "alert_fired": true
}
```

## 5. Verify the Alert Dispatch
Once the `risk_score` hits the `RISK_ALERT_THRESHOLD` (70+), it triggers the Twilio dispatch and logs the alert. Because we only have placeholder credentials in `.env`, the system gracefully caught the authentication error and recorded the alert as `simulated`.
**Endpoint:** `GET /alerts`
```json
{
  "alerts": [
    {
      "zone_id": "zone-c",
      "zone_label": "Paddy Store C (leaky roof)",
      "risk_score": 80,
      "message": "🔴 *Godown Alert* — Paddy Store C (leaky roof)\nRisk Score  : *80/100*\nZone ID     : zone-c\nTemperature : 27.5°C\nHumidity    : 76.5%\nGas (CO₂)  : 701.5 ppm\nTime        : 2026-07-30 17:06 UTC\nAction: Inspect zone immediately and improve ventilation.",
      "channel": "simulated",
      "timestamp": "2026-07-30T17:06:42.659991+00:00"
    }
  ]
}
```
> [!TIP]
> The backend automatically respects the 10-minute cooldown rule. Subsequent hits to `/risk/zone-c` while it remains in the red zone won't spam additional alerts, they will just report `"alert_fired": false` until the cooldown expires.
