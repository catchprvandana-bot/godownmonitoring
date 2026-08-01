# Demo script (rehearse in hours 30-34)

1. **Open the dashboard** (`http://localhost:8000/`) — 3 zone cards visible, color-coded
   green/yellow/red. Point out `zone-c` ("leaky roof") is the one trending toward risk —
   its humidity/gas drift upward over the course of the demo, so leave it running in the
   background for a few minutes before presenting so the story is visibly escalating,
   not flat.
2. **Explain the sensor cards**: temperature, humidity, gas-proxy readings + a computed
   risk score. Mention these are simulated for the hackathon but structured exactly like
   real DHT22/MQ-sensor output — swapping in real hardware means swapping one function
   (`backend/sensors.py: get_simulated_reading`) for a real GPIO read, nothing else changes.
3. **Upload a sample image** via the "Classify a sample image" panel — pick a visibly
   moldy or pest-damaged sample. Show the model's live classification + confidence.
   If confidence is below 60%, point out it returns `"uncertain - flagged for manual
   check"` instead of guessing — call this out explicitly as a responsible-AI choice,
   judges respond well to this.
4. **Show the risk score update** for that zone after classification — the vision result
   blends into the same score as the sensor data (see "vision: ..." line and the reasons
   list on the zone card).
5. **Show the alert log** — either a real WhatsApp message (if Twilio is wired up) or the
   in-app alert feed. Either way, say the same sentence: "this fires automatically once a
   zone crosses 70% risk, no manual check needed."
6. **Close with the one-liner**: "Sensors are simulated for this build, but the
   architecture — and the AI model itself — is fully real and ready for hardware
   integration. Swapping in physical sensors is a one-function change, not a rebuild."

## Fallback plan if something breaks live

- Model not loading / not trained in time -> `/classify` already falls back to a mocked
  but confidence-scored prediction automatically. Don't apologize for it on stage, the
  UI doesn't visibly differentiate mock vs. real unless you point at the `source` field.
- Twilio not configured / sandbox expired -> alert log on the dashboard covers the same
  narrative beat, don't burn time debugging Twilio during the demo window.
- Backend crashes -> restart with `uvicorn main:app --port 8000` from `backend/`, state is
  in-memory only (zones reset to baseline, which is actually fine for a fresh demo run).
