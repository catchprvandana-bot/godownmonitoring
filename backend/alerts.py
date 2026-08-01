"""Alert dispatch: WhatsApp/SMS via PyWhatKit, else an in-memory
alert log the dashboard can poll.

PyWhatKit is activated when ALERT_WHATSAPP_TO is set.
If the recipient is absent, the app falls back to a local alert log.

Environment variables (see .env.example):
    ALERT_WHATSAPP_TO        Recipient WhatsApp number (e.g. +91XXXXXXXXXX)
    RISK_ALERT_THRESHOLD     Score 0-100 that fires an alert (default: 70)
    ALERT_COOLDOWN_MINUTES   Re-alert cooldown per zone (default: 10)
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Load .env if present (python-dotenv is optional — gracefully skip if missing) ─
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed; fall back to OS env vars only

# ── Configuration ─────────────────────────────────────────────────────────────
ALERT_TO              = os.environ.get("ALERT_WHATSAPP_TO")

RISK_ALERT_THRESHOLD  = int(os.environ.get("RISK_ALERT_THRESHOLD", "70"))
ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "0"))

# ── Internal state ────────────────────────────────────────────────────────────
# Maps zone_id → datetime of last alert (for time-based cooldown)
_last_alerted_at: dict[str, datetime] = {}
_last_whatsapp_alerted_at: dict[str, datetime] = {}
_alert_log: list[dict] = []
_last_whatsapp_error: str | None = None


def _severity_emoji(risk_score: int) -> str:
    if risk_score >= 85:
        return "🔴🚨"
    if risk_score >= 70:
        return "🔴"
    return "🟡"


def _build_message(zone_id: str, zone_label: str, risk_score: int, sensor: dict | None = None) -> str:
    emoji = _severity_emoji(risk_score)
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"{emoji} *Godown Alert* — {zone_label}",
        f"Risk Score  : *{risk_score}/100*",
        f"Zone ID     : {zone_id}",
    ]
    if sensor:
        lines += [
            f"Temperature : {sensor.get('temperature_c', 'N/A')}°C",
            f"Humidity    : {sensor.get('humidity_pct', 'N/A')}%",
            f"Gas (CO₂)  : {sensor.get('gas_ppm', 'N/A')} ppm",
        ]
    lines += [
        f"Time        : {now}",
        "Action: Inspect zone immediately and improve ventilation.",
    ]
    return "\n".join(lines)


import threading
_whatsapp_lock = threading.Lock()

def _send_whatsapp(body: str) -> bool:
    """Send a WhatsApp message via PyWhatKit. Returns True on success."""
    # We have removed pywhatkit backend dispatch in favor of frontend redirects.
    return False
    
def _is_in_cooldown(zone_id: str) -> bool:
    """Return True if this zone was alerted within the cooldown window."""
    last = _last_alerted_at.get(zone_id)
    if last is None:
        return False
    if ALERT_COOLDOWN_MINUTES <= 0:
        return True  # 0 means alert once per incident, never re-alert until recovery
    return datetime.now(timezone.utc) - last < timedelta(minutes=ALERT_COOLDOWN_MINUTES)


def maybe_alert(zone_id: str, zone_label: str, risk_score: int, sensor: dict | None = None) -> dict | None:
    """Fire an alert if risk crosses the threshold and the zone is not in cooldown.

    Args:
        zone_id:    Unique zone identifier (e.g. "zone-c").
        zone_label: Human-readable zone name (e.g. "Paddy Store C").
        risk_score: Combined risk score 0–100.
        sensor:     Optional dict with temperature_c, humidity_pct, gas_ppm for
                    inclusion in the alert body.

    Returns:
        The alert log entry dict if an alert was fired, else None.
    """
    if risk_score < RISK_ALERT_THRESHOLD:
        # Zone recovered with hysteresis — clear cooldown so it can alert again if it worsens
        # We require it to drop at least 5 points below the threshold to prevent spam.
        if risk_score <= (RISK_ALERT_THRESHOLD - 5):
            _last_alerted_at.pop(zone_id, None)
            _last_whatsapp_alerted_at.pop(zone_id, None)
        return None

    in_cooldown = _is_in_cooldown(zone_id)
    needs_whatsapp = risk_score > 75
    
    wa_cooldown = False
    last_wa = _last_whatsapp_alerted_at.get(zone_id)
    if last_wa is not None:
        if ALERT_COOLDOWN_MINUTES <= 0:
            wa_cooldown = True
        else:
            wa_cooldown = datetime.now(timezone.utc) - last_wa < timedelta(minutes=ALERT_COOLDOWN_MINUTES)
            
    if in_cooldown:
        if needs_whatsapp and not wa_cooldown:
            pass # allow escalation to WhatsApp
        else:
            return None  # Already alerted recently; suppress duplicate spam

    # Fire the alert
    _last_alerted_at[zone_id] = datetime.now(timezone.utc)
    message    = _build_message(zone_id, zone_label, risk_score, sensor)
    
    needs_redirect = False
    if needs_whatsapp and not wa_cooldown:
        _last_whatsapp_alerted_at[zone_id] = datetime.now(timezone.utc)
        needs_redirect = True

    entry = {
        "zone_id":   zone_id,
        "zone_label": zone_label,
        "risk_score": risk_score,
        "message":   message,
        "channel":   "whatsapp_redirect" if needs_redirect else "simulated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "whatsapp_to": ALERT_TO if needs_redirect else None,
        "needs_whatsapp_redirect": needs_redirect
    }
    _alert_log.append(entry)
    return entry


def get_alert_log(limit: int = 50) -> list[dict]:
    return list(reversed(_alert_log[-limit:]))


def whatsapp_configured() -> bool:
    """Return True if real WhatsApp dispatch is active."""
    return bool(ALERT_TO)


def get_whatsapp_error() -> str | None:
    """Return the last WhatsApp send error string, or None if no error."""
    return _last_whatsapp_error
