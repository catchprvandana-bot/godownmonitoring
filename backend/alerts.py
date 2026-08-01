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
ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "1"))

# ── Internal state ────────────────────────────────────────────────────────────
# Maps zone_id → datetime of last alert (for time-based cooldown)
_last_alerted_at: dict[str, datetime] = {}
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


def _send_whatsapp(body: str) -> bool:
    """Send a WhatsApp message via PyWhatKit/Webbrowser. Returns True on success."""
    global _last_whatsapp_error
    if not ALERT_TO:
        return False
    try:
        import time
        import urllib.parse
        import webbrowser
        import pyautogui

        print(f"[alerts.py] Attempting to send WhatsApp message to {ALERT_TO}...")
        # Clean the number (remove 'whatsapp:' prefix if present from old config)
        to_number = ALERT_TO.replace("whatsapp:", "")
        print(f"[alerts.py] Cleaned number: {to_number}. Launching browser...")
        
        # Build WhatsApp Web URL
        parsed_message = urllib.parse.quote(body)
        url = f"https://web.whatsapp.com/send?phone={to_number}&text={parsed_message}"
        
        # Open in default browser
        webbrowser.open(url)
        
        # Wait for WhatsApp Web to fully load and the chat box to be ready
        time.sleep(20)
        
        # Press Enter to send the message automatically
        pyautogui.press("enter")
        
        print(f"[alerts.py] WhatsApp message dispatched automatically.")
        _last_whatsapp_error = None
        return True
    except Exception as exc:
        _last_whatsapp_error = str(exc)
        error_entry = {
            "zone_id":   "system",
            "message":   f"[WhatsApp ERROR] {exc}",
            "channel":   "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _alert_log.append(error_entry)
        print(f"[alerts.py] WhatsApp send failed: {exc}")
        return False
    
def _is_in_cooldown(zone_id: str) -> bool:
    """Return True if this zone was alerted within the cooldown window."""
    last = _last_alerted_at.get(zone_id)
    if last is None:
        return False
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
        # Zone recovered — clear cooldown so it can alert again if it worsens
        _last_alerted_at.pop(zone_id, None)
        return None

    if _is_in_cooldown(zone_id):
        return None  # Already alerted recently; suppress duplicate spam

    # Fire the alert
    _last_alerted_at[zone_id] = datetime.now(timezone.utc)
    message    = _build_message(zone_id, zone_label, risk_score, sensor)
    sent_live  = _send_whatsapp(message)

    entry = {
        "zone_id":   zone_id,
        "zone_label": zone_label,
        "risk_score": risk_score,
        "message":   message,
        "channel":   "whatsapp" if sent_live else "simulated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
