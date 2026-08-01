const API_BASE = ""; // same origin - backend serves this file too
const POLL_MS = 4000;

// DOM references — guarded so missing elements never throw on page load
const zonesEl        = document.getElementById("zones");
const zoneSelect     = document.getElementById("classify-zone");
const classifyForm   = document.getElementById("classify-form");
const classifyResult = document.getElementById("classify-result");
const alertLogEl     = document.getElementById("alert-log");
const statusDetail   = document.getElementById("status-detail");
const fileInput      = document.getElementById("classify-file");
const fileHint       = document.getElementById("file-hint");
const alertBadge     = document.getElementById("alert-count-badge");
const sumGreenNum    = document.getElementById("sum-green-num");
const sumYellowNum   = document.getElementById("sum-yellow-num");
const sumRedNum      = document.getElementById("sum-red-num");

// Update the file-hint label whenever the user picks a file
if (fileInput && fileHint) {
  fileInput.addEventListener("change", () => {
    fileHint.textContent = fileInput.files.length ? fileInput.files[0].name : "No file chosen";
  });
}

let zoneIds = [];
let previousAlertCount = -1;

let audioCtx = null;
function initAudio() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}
document.addEventListener('click', initAudio, { once: true });

async function fetchJSON(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function playBuzzer() {
  try {
    initAudio();
    // Play 3 loud beeps
    for (let i = 0; i < 3; i++) {
      const osc = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      
      osc.type = 'square';
      osc.frequency.setValueAtTime(1000, audioCtx.currentTime + i * 0.3);
      
      // Envelope to avoid popping and ensure it is loud
      gainNode.gain.setValueAtTime(0, audioCtx.currentTime + i * 0.3);
      gainNode.gain.linearRampToValueAtTime(0.5, audioCtx.currentTime + i * 0.3 + 0.05);
      gainNode.gain.setValueAtTime(0.5, audioCtx.currentTime + i * 0.3 + 0.15);
      gainNode.gain.linearRampToValueAtTime(0, audioCtx.currentTime + i * 0.3 + 0.2);
      
      osc.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      osc.start(audioCtx.currentTime + i * 0.3);
      osc.stop(audioCtx.currentTime + i * 0.3 + 0.25);
    }
  } catch (e) {
    console.error("Audio playback failed", e);
  }
}

function showToast(message, type = 'success') {
  let container = document.getElementById('toaster-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toaster-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-message">${message}</span>
    <button class="toast-close">&times;</button>
  `;

  container.appendChild(toast);

  toast.querySelector('.toast-close').addEventListener('click', () => {
    toast.classList.add('fade-out');
    toast.addEventListener('animationend', () => toast.remove());
  });

  setTimeout(() => {
    if (toast.parentElement) {
      toast.classList.add('fade-out');
      toast.addEventListener('animationend', () => toast.remove());
    }
  }, 5000);
}

function renderZoneCard(risk) {
  const level = risk.risk_level;
  const s = risk.sensor_data;
  const vision = risk.vision
    ? `<div class="readings">vision: ${risk.vision.label} (${Math.round(risk.vision.confidence * 100)}%)</div>`
    : "";
  const reasons = risk.reasons.length
    ? `<ul class="reasons">${risk.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>`
    : "";

  return `
    <article class="zone-card ${level}" id="card-${risk.zone_id}">
      <h3>${s.label || risk.zone_id}</h3>
      <div class="zone-id">${risk.zone_id}</div>
      <div class="risk-score">${risk.risk_score}%</div>
      <div class="readings">
        <span>${s.temperature_c}&deg;C</span>
        <span>${s.humidity_pct}% RH</span>
        <span>${s.gas_ppm} ppm</span>
      </div>
      ${vision}
      ${reasons}
    </article>
  `;
}

async function refreshZones() {
  if (!zonesEl) return;
  const results = await Promise.all(zoneIds.map((id) => fetchJSON(`/risk/${id}`).catch(() => null)));
  const valid = results.filter(Boolean);
  zonesEl.innerHTML = valid.map(renderZoneCard).join("");

  // Update summary bar counts
  const counts = { green: 0, yellow: 0, red: 0 };
  valid.forEach((r) => { if (counts[r.risk_level] !== undefined) counts[r.risk_level]++; });
  if (sumGreenNum)  sumGreenNum.textContent  = counts.green;
  if (sumYellowNum) sumYellowNum.textContent = counts.yellow;
  if (sumRedNum)    sumRedNum.textContent    = counts.red;
}

async function refreshAlerts() {
  if (!alertLogEl) return;
  const { alerts } = await fetchJSON("/alerts");
  if (alertBadge) alertBadge.textContent = alerts.length;
  
  if (previousAlertCount === -1) {
    // First load, don't buzz
    previousAlertCount = alerts.length;
  } else if (alerts.length > previousAlertCount) {
    // New alerts arrived!
    const newestAlert = alerts[0];
    
    // Play the buzzer for the alert
    playBuzzer();
    
    // Trigger redirect if backend marked it for WhatsApp and we have a number
    if (newestAlert.needs_whatsapp_redirect && newestAlert.whatsapp_to) {
        const phone = newestAlert.whatsapp_to.replace("whatsapp:", "").replace("+", "");
        const text = encodeURIComponent(newestAlert.message);
        
        const popup = window.open(`https://wa.me/${phone}?text=${text}`, "_blank");
        if (!popup || popup.closed || typeof popup.closed == 'undefined') {
            // Popup blocker prevented the new tab, redirect current window instead
            window.location.href = `https://wa.me/${phone}?text=${text}`;
        }
    }
    
    previousAlertCount = alerts.length;
  }

  if (!alerts.length) {
    alertLogEl.innerHTML = `<li class="empty">No alerts yet.</li>`;
    return;
  }
  alertLogEl.innerHTML = alerts
    .map(
      (a) => `
      <li>
        <span class="timestamp">${new Date(a.timestamp).toLocaleTimeString()} &middot; ${a.channel}</span>
        ${a.message}
      </li>`
    )
    .join("");
}

async function init() {
  try {
    if (statusDetail) statusDetail.textContent = "Connecting…";
    const { zones } = await fetchJSON("/zones");
    zoneIds = zones;
    if (zoneSelect) {
      zoneSelect.innerHTML = zones.map((z) => `<option value="${z}">${z}</option>`).join("");
    }

    await refreshZones();
    await refreshAlerts();

    if (statusDetail) statusDetail.textContent = `${zones.length} zone(s) live`;

    setInterval(refreshZones, POLL_MS);
    setInterval(refreshAlerts, POLL_MS);
  } catch (err) {
    // Surface connection errors visibly rather than crashing silently
    if (statusDetail) statusDetail.textContent = `Connection error: ${err.message}`;
    if (zonesEl) zonesEl.innerHTML = `<p style="color:#d1352b;padding:16px">⚠ Could not reach the backend. Is uvicorn running? (${err.message})</p>`;
  }
}

// Guard: only attach listener if the form element exists
if (classifyForm) {
  classifyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    // Re-read file from the guarded fileInput reference
    const file = fileInput ? fileInput.files[0] : null;
    if (!file) {
      if (classifyResult) classifyResult.textContent = "Please select an image first.";
      return;
    }

    // Create image preview URL
    const previewUrl = URL.createObjectURL(file);

    const formData = new FormData();
    formData.append("file", file);
    if (zoneSelect) formData.append("zone_id", zoneSelect.value);

    if (classifyResult) classifyResult.innerHTML = `<div class="classify-loading"><span class="classify-spinner"></span> Analyzing image…</div>`;
    try {
      const result = await fetchJSON("/classify", { method: "POST", body: formData });

      if (zoneSelect && zoneSelect.value === 'zone-c' && result.risk_score >= 85) {
        playBuzzer();
        if (result.whatsapp_to) {
            const phone = result.whatsapp_to.replace("whatsapp:", "").replace("+", "");
            const text = encodeURIComponent("Godown Alert! CV Classification detected high risk (Score: " + result.risk_score + "/100). Please inspect immediately.");
            
            const popup = window.open(`https://wa.me/${phone}?text=${text}`, "_blank");
            if (!popup || popup.closed || typeof popup.closed == 'undefined') {
                window.location.href = `https://wa.me/${phone}?text=${text}`;
            }
        }
      }

      // Label → display config
      const labelConfig = {
        healthy:       { icon: "✅", color: "#22c55e", bg: "rgba(34,197,94,0.12)",  text: "Healthy" },
        mold:          { icon: "🦠", color: "#ef4444", bg: "rgba(239,68,68,0.12)",  text: "Mold Detected" },
        pest_damage:   { icon: "🐛", color: "#f97316", bg: "rgba(249,115,22,0.12)", text: "Pest Damage" },
        discoloration: { icon: "🟡", color: "#eab308", bg: "rgba(234,179,8,0.12)",  text: "Discoloration" },
        uncertain:     { icon: "❓", color: "#9aa0ab", bg: "rgba(154,160,171,0.12)", text: "Uncertain" },
      };
      const cfg = labelConfig[result.label] || labelConfig.uncertain;
      const confPct = Math.round(result.confidence * 100);
      const note = result.note ? `<div class="cr-note">⚠ ${result.note}</div>` : "";

      let alertHtml = "";
      if (result.alert_fired !== undefined) {
        if (result.alert_fired) {
          alertHtml = `<div class="cr-alert fired">⚠️ ALERT FIRED via ${result.alert_channel} · Risk ${result.risk_score}/100</div>`;
        } else {
          alertHtml = `<div class="cr-alert safe">Risk Score: ${result.risk_score}/100</div>`;
        }
      }

      if (classifyResult) {
        classifyResult.innerHTML = `
          <div class="cr-card">
            <img class="cr-preview" src="${previewUrl}" alt="Uploaded sample" />
            <div class="cr-body">
              <div class="cr-badge" style="background:${cfg.bg}; color:${cfg.color}; border-color:${cfg.color};">
                <span class="cr-icon">${cfg.icon}</span>
                <span class="cr-label">${cfg.text}</span>
              </div>
              <div class="cr-conf">
                <div class="cr-conf-bar-track">
                  <div class="cr-conf-bar-fill" style="width:${confPct}%; background:${cfg.color};"></div>
                </div>
                <span class="cr-conf-pct">${confPct}%</span>
              </div>
              <div class="cr-meta">Source: ${result.source}</div>
              ${note}
              ${alertHtml}
            </div>
          </div>`;
      }

      showToast(`${cfg.icon} ${cfg.text} — ${confPct}% confidence`, 'success');

      // Clear the image
      if (fileInput) fileInput.value = "";
      if (fileHint) fileHint.textContent = "No file chosen";

      // Refresh zones and alerts immediately — don't wait for the 4s poll
      await refreshZones();
      await refreshAlerts();
    } catch (err) {
      if (classifyResult) classifyResult.textContent = `Error: ${err.message}`;
      showToast(`Error: ${err.message}`, 'error');
    }
  });
}

init();

/* 
================================================================================
Godown Monitoring System - LinkedIn Post Options
================================================================================

Option 1: The "Tech-Focused & Problem Solver" (Recommended for recruiters & engineers)
--------------------------------------------------------------------------------
Did you know that millions of tons of harvested grains are lost every year simply due to poor storage conditions? 🌾📉

I wanted to see how technology could help solve this, so I built the Godown Monitoring System—an end-to-end AgriTech platform that detects and predicts grain spoilage in real-time. 

Here is how it works under the hood:
📡 IoT Sensor Tracking: Continuously monitors Temperature, Humidity, and CO₂ levels to calculate dynamic spoilage risk scores.
👁️ Computer Vision: Integrated a MobileNetV2 deep learning model to visually inspect uploaded images of grains and classify them for mold, pest damage, or discoloration.
🚨 Automated Action: If a storage zone reaches a critical risk threshold, the system automatically dispatches an emergency WhatsApp alert to the facility manager via Twilio.
💻 Tech Stack: FastAPI (Backend), TensorFlow/Keras (ML), Vanilla JS/HTML/CSS (Dashboard), and Twilio API.

Building this taught me so much about combining real-time data streams with AI inference and third-party API integrations. 

I’ve attached a demo of the dashboard catching a "leaky roof" scenario! Let me know what you think in the comments. 👇

#AgriTech #ComputerVision #IoT #FastAPI #MachineLearning #FoodSecurity #Python #SoftwareEngineering #TechForGood #Developer

Option 2: The "Story-Driven & Impact" (Recommended for a broader audience and founders)
--------------------------------------------------------------------------------
We spend so much effort growing food, but what happens after the harvest? 🤔 

A massive amount of grain spoils in storage facilities (godowns) before it ever reaches the market. To tackle this, I built an intelligent Godown Monitoring System to catch spoilage before it destroys the harvest.

I combined IoT (monitoring temp, humidity, and CO₂) with AI (Computer Vision to visually detect mold and pests). The system calculates a real-time risk score for different storage zones. If things get dangerous—like a spike in humidity from a leaky roof—it instantly fires off a WhatsApp alert to the manager so they can save the crop. 📲🌾

This project was an incredible journey into full-stack development, bringing together a FastAPI backend, TensorFlow for the vision model, and Twilio for automated alerts.

Check out the video below to see the real-time dashboard and AI classification in action! 

#AgriTech #Innovation #ArtificialIntelligence #WebDevelopment #TechForGood #IoT #MachineLearning #Engineering

Option 3: Short, Punchy & Demo-Heavy (Recommended if you have a great video demo)
--------------------------------------------------------------------------------
Just wrapped up my latest full-stack project: an AI-powered Godown Monitoring System to prevent grain spoilage! 🚀🌾

🔹 The Problem: Grains rotting in storage due to unmonitored environmental changes.
🔹 The Solution: A real-time dashboard that tracks IoT data (Temp/Humidity/CO₂) and uses Computer Vision to detect mold. 
🔹 The Result: Automated WhatsApp alerts sent to managers the second a storage zone becomes critical. 

Built with: Python, FastAPI, TensorFlow (MobileNetV2), Twilio, and JavaScript. 

Check out the demo below where the system detects a critical spike and dispatches an alert! 👇

#AgriTech #MachineLearning #FastAPI #ComputerVision #DeveloperPortfolio #Python
================================================================================
*/
