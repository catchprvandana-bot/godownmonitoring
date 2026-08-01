# Godown Monitoring System - Testing & Demo Guide

## Screen-Level Testing Flow (Dashboard UI)

### 1. Initial Dashboard Load
- **Action**: Open your browser and go to `http://localhost:8000/`. (The FastAPI backend serves the dashboard statically).
- **Expected Screen**: You should see the main dashboard interface. 
- **Verify**: 
  - The System Status indicator should say "Connected" (or show a green status light).
  - You should see cards/panels for three zones: "Zone A", "Zone B", and "Zone C".
  - The initial risk levels for all zones should generally be Green (Low Risk) or Yellow (Moderate Risk), and simulated sensor readings (Temperature, Humidity, Gas) should be visible and updating every few seconds.

### 2. Simulating Risk Escalation (The "Leaky Roof" Scenario)
- **Action**: Keep the dashboard open and focus your attention on **Zone C (Paddy Store C)**.
- **Expected Screen**: The simulation engine (`backend/sensors.py`) is hardcoded to simulate a worsening environment for Zone C. Watch its sensor values over 1-2 minutes.
- **Verify**: 
  - Humidity will naturally drift up towards >75%.
  - Gas (CO2) will drift up towards >700 ppm.
  - The Risk Score circle/indicator for Zone C will climb from ~45 (Yellow) to 80+ (Red).
  - The UI for Zone C will turn Red, indicating a High Spoilage Risk.

### 3. Triggering and Viewing WhatsApp Alerts
- **Action**: Once Zone C hits a risk score of 70+, check the "Alert Log" section on the dashboard. (If you filled out your `.env` with Twilio credentials, also check your phone).
- **Expected Screen**: A new alert entry appears automatically.
- **Verify**:
  - The UI Alert Log will show a critical entry: `🔴🚨 *Godown Alert* — Paddy Store C`.
  - It will display the exact snapshot of Temperature, Humidity, and Gas that triggered the alert.
  - *(If Twilio is configured)*: Your phone will receive the identical formatted WhatsApp message from the Twilio Sandbox number.

### 4. Testing the Computer Vision Integration
- **Action**: In the dashboard, locate the "Upload Image" or "Classify" section for a specific zone. Upload one of the synthetic images we generated locally (e.g., from `ml/dataset/val/mold/mold_0000.jpg`).
- **Expected Screen**: The dashboard sends this to the `/classify` API and updates the risk score based on the vision result.
- **Verify**:
  - The backend returns the classification (`mold`, `healthy`, `pest_damage`, or `discoloration`).
  - If a negative condition like `mold` is detected, the Risk Score for that zone will immediately jump by +30 points.
  - The "Reasons" log will now append: `vision classified 'mold' (+30)`.

---

## How to Train the Model for Testing

Because TensorFlow does not currently support Python 3.14 (your local environment), we have set up two ways to handle the Machine Learning component for testing and demoing:

### Option A: Use the Built-in Mock Classifier (Fastest for UI Testing)
If the file `backend/model/spoilage_model.h5` does not exist, the backend automatically falls back to a **mock classifier**. 
- You don't need to train anything. 
- When you upload an image in the UI, the backend will randomly assign a label (`healthy`, `mold`, etc.) with a simulated confidence score so you can test how the UI reacts to different vision results without waiting for a real neural network to process it.

### Option B: Train the Real Model via Google Colab (For the Final Demo)
To use a real neural network, you must train it in a Python 3.10-3.12 environment. We have provided a ready-to-run Jupyter Notebook for Google Colab (which provides free GPUs and a compatible Python environment).

1. **Open Colab**:
   Go to [Google Colab](https://colab.research.google.com/) and upload the file from this project: `ml/train_spoilage_colab.ipynb`.

2. **Configure the Notebook**:
   - Go to `Runtime > Change runtime type` in the top menu.
   - Select **GPU (T4)** as the hardware accelerator and save.

3. **Run the Notebook**:
   - Run the cells one by one (or select `Runtime > Run all`). 
   - *Note: Cell 2 in the notebook automatically generates the synthetic dataset right inside Colab for you, so you don't even need to upload any local images!*
   - Let the notebook train the MobileNetV2 model (this takes ~5 minutes on a GPU).

4. **Download the Model**:
   The final cell in the notebook will automatically trigger a download of a file named `spoilage_model.h5` to your computer.

5. **Load it into the Backend**:
   - Copy `spoilage_model.h5` into your local `backend/model/` directory.
   - Stop and restart your backend server:
     ```powershell
     py -m uvicorn backend.main:app --reload --port 8000
     ```
   - The API will start up and log `model_loaded: true`. The dashboard will now use real AI inference for uploaded images!
