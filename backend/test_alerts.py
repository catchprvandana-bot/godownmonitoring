# -*- coding: utf-8 -*-
"""Standalone Twilio WhatsApp alert test.

Sends a single test alert to ALERT_WHATSAPP_TO without starting the server.
Useful for verifying your Twilio credentials and phone number are wired up
correctly before running a live demo.

Usage (from project root):
    python -m backend.test_alerts

Requires .env to be configured (see .env.example).
"""

import sys
import io
from pathlib import Path

# Force UTF-8 output on Windows to handle Unicode characters in alert messages
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow running as `python -m backend.test_alerts` from the project root
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from backend import alerts  # noqa: E402 — import after sys.path tweak


def main():
    print("=" * 60)
    print("  Godown Monitoring - Twilio WhatsApp Alert Test")
    print("=" * 60)

    to_val  = alerts.ALERT_TO or "[NOT SET]"
    active  = "[YES - live]" if alerts.whatsapp_configured() else "[NO - simulated mode]"

    print(f"\n[CONFIG]")
    print(f"   ALERT_WHATSAPP_TO   : {to_val}")
    print(f"   Risk threshold      : {alerts.RISK_ALERT_THRESHOLD}")
    print(f"   Cooldown (min)      : {alerts.ALERT_COOLDOWN_MINUTES}")
    print(f"   WhatsApp active     : {active}")

    print("\n[TEST] Firing test alert for zone-c (risk=85, synthetic sensor data)...")

    fake_sensor = {
        "zone_id": "zone-c",
        "label": "Paddy Store C (leaky roof)",
        "temperature_c": 33.7,
        "humidity_pct": 78.4,
        "gas_ppm": 721.0,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }

    # Force-bypass the cooldown for the test by clearing internal state
    alerts._last_alerted_at.clear()
    alerts._last_whatsapp_alerted_at.clear()

    entry = alerts.maybe_alert(
        zone_id="zone-c",
        zone_label="Paddy Store C (leaky roof)",
        risk_score=85,
        sensor=fake_sensor,
    )

    if entry is None:
        print("\n[FAIL] No alert fired - check threshold / cooldown logic.")
        sys.exit(1)

    print(f"\n[OK] Alert entry created:")
    for k, v in entry.items():
        if k == "message":
            print(f"   {k}:")
            for line in v.splitlines():
                print(f"      {line}")
        else:
            print(f"   {k}: {v}")

    if entry["channel"] == "whatsapp":
        print(f"\n[SENT] WhatsApp message sent to {alerts.ALERT_TO}")
    else:
        print("\n[SIMULATED] Alert logged in simulated mode (no WhatsApp sent).")
        print("   -> Fill in .env with a real WhatsApp number to enable live dispatch.")

    log = alerts.get_alert_log()
    print(f"\n[LOG] Alert log entries: {len(log)}")


if __name__ == "__main__":
    main()
