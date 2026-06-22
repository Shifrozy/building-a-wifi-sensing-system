"""
WiFi Sensing System — Configuration
====================================
Central configuration for rooms, scanning parameters, model settings, and server config.
"""

import os

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FINGERPRINT_DIR = os.path.join(DATA_DIR, "fingerprints")
MODEL_DIR = os.path.join(DATA_DIR, "models")

# Create directories if they don't exist
for d in [DATA_DIR, FINGERPRINT_DIR, MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

# ─── Room Definitions ────────────────────────────────────────────────────────
# Each room has an id, name, color (for dashboard), and icon
ROOMS = [
    {"id": "room_1", "name": "Bedroom",      "color": "#6366f1", "icon": "🛏️"},
    {"id": "room_2", "name": "Living Room",   "color": "#8b5cf6", "icon": "🛋️"},
    {"id": "room_3", "name": "Kitchen",       "color": "#ec4899", "icon": "🍳"},
    {"id": "room_4", "name": "Bathroom",      "color": "#14b8a6", "icon": "🚿"},
]

# ─── WiFi Scanner Settings ───────────────────────────────────────────────────
SCAN_INTERVAL = 2          # seconds between scans
SCAN_RETRIES = 3           # retry count on scan failure
MIN_RSSI = -100            # minimum RSSI value (used for missing APs)
SMOOTHING_WINDOW = 3       # number of scans to average for stability

# ─── Calibration Settings ────────────────────────────────────────────────────
CALIBRATION_DURATION = 30  # seconds to collect data per room
CALIBRATION_SCANS = 15     # number of scans per calibration session
MIN_APS_REQUIRED = 2       # minimum access points needed for calibration

# ─── ML Model Settings ───────────────────────────────────────────────────────
MODEL_FILE = os.path.join(MODEL_DIR, "wifi_model.pkl")
SCALER_FILE = os.path.join(MODEL_DIR, "wifi_scaler.pkl")
AP_LIST_FILE = os.path.join(MODEL_DIR, "ap_list.json")
MODEL_PARAMS = {
    "n_estimators": 100,
    "max_depth": 10,
    "random_state": 42,
    "n_jobs": -1,
}
CONFIDENCE_THRESHOLD = 0.4  # minimum confidence to report a room

# ─── Prediction Settings ─────────────────────────────────────────────────────
PREDICTION_HISTORY_SIZE = 5  # number of predictions to keep for majority voting
MOVEMENT_COOLDOWN = 3        # seconds before reporting room change

# ─── Device Tracker Settings ─────────────────────────────────────────────────
DEVICE_SCAN_INTERVAL = 10   # seconds between device scans
KNOWN_DEVICES_FILE = os.path.join(DATA_DIR, "known_devices.json")
ROUTER_IP = "192.168.100.1"  # default router IP (from user's ping test)
NETWORK_SUBNET = "192.168.100"  # subnet for ARP scanning

# ─── Server Settings ─────────────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000
DEBUG_MODE = True
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

# ─── History Settings ────────────────────────────────────────────────────────
MAX_HISTORY_ENTRIES = 100  # max movement history entries to keep
HISTORY_FILE = os.path.join(DATA_DIR, "movement_history.json")
