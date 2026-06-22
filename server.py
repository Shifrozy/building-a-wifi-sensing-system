"""
WiFi Sense — Flask API Server
===============================
Serves the dashboard and provides API endpoints for:
- 3D Radar visualization (motion detection)
- Room detection status
- WiFi signal data
- Device tracking
- Calibration control
- Model training
"""

import os
import sys
import json
import time
import threading
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from scanner.wifi_scanner import scan_wifi, scan_wifi_averaged
from scanner.device_tracker import scan_network_devices, update_known_devices
from ml.fingerprint import (
    collect_fingerprint, save_fingerprint, load_fingerprint,
    get_calibration_status, delete_fingerprint
)
from ml.model import train_model, is_model_trained
from ml.predictor import RoomPredictor
from scanner.motion_detector import MotionDetector

# ─── Flask App ───────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
CORS(app)

# ─── Global State ────────────────────────────────────────────────
predictor = RoomPredictor()
motion_detector = MotionDetector()
latest_scan = {"networks": [], "timestamp": 0}
latest_devices = {"devices": [], "timestamp": 0}
latest_prediction = {"room_id": None, "confidence": 0, "probabilities": {}}
latest_radar = {}
calibration_state = {"active": False, "room_id": None, "progress": 0, "done": False}
scan_thread = None
scan_running = False


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard page."""
    return send_from_directory(config.DASHBOARD_DIR, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from dashboard directory."""
    return send_from_directory(config.DASHBOARD_DIR, filename)


# ═══════════════════════════════════════════════════════════════════
#  3D RADAR API
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/radar')
def api_radar():
    """Get 3D radar data — motion detection + signal data."""
    return jsonify(latest_radar if latest_radar else {
        "motion_detected": False,
        "presence_detected": False,
        "motion_intensity": 0,
        "detection_confidence": 0,
        "person_position": {"x": 0, "z": 0},
        "signal_data": [],
        "scan_count": 0,
        "baseline_ready": False,
        "num_networks": 0,
        "timestamp": 0,
    })


@app.route('/api/radar/reset', methods=['POST'])
def api_radar_reset():
    """Reset motion detector baseline."""
    motion_detector.reset_baseline()
    return jsonify({"success": True, "message": "Baseline reset"})


# ═══════════════════════════════════════════════════════════════════
#  API ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/status')
def api_status():
    """Get current detection status."""
    global latest_prediction
    
    room_info = None
    if latest_prediction.get("room_id"):
        for room in config.ROOMS:
            if room["id"] == latest_prediction["room_id"]:
                room_info = room
                break
    
    return jsonify({
        "current_room": latest_prediction.get("room_id"),
        "room_name": latest_prediction.get("room_name", "Unknown"),
        "room_icon": room_info["icon"] if room_info else "📍",
        "confidence": latest_prediction.get("confidence", 0),
        "probabilities": latest_prediction.get("all_probabilities", {}),
        "num_networks": latest_prediction.get("num_networks", 0),
        "model_loaded": predictor.model is not None,
        "error": latest_prediction.get("error"),
        "timestamp": latest_prediction.get("timestamp", 0),
    })


@app.route('/api/rooms')
def api_rooms():
    """Get all room definitions."""
    return jsonify({
        "rooms": config.ROOMS,
    })


@app.route('/api/signals')
def api_signals():
    """Get latest WiFi signal scan data."""
    return jsonify({
        "networks": latest_scan.get("networks", []),
        "timestamp": latest_scan.get("timestamp", 0),
        "count": len(latest_scan.get("networks", [])),
    })


@app.route('/api/devices')
def api_devices():
    """Get connected network devices."""
    return jsonify({
        "devices": latest_devices.get("devices", []),
        "timestamp": latest_devices.get("timestamp", 0),
        "count": len(latest_devices.get("devices", [])),
    })


@app.route('/api/history')
def api_history():
    """Get movement history."""
    history = predictor.get_movement_history(limit=20)
    return jsonify({
        "history": history,
        "count": len(history),
    })


@app.route('/api/calibrate/status')
def api_calibrate_status():
    """Get calibration status for all rooms."""
    status = get_calibration_status()
    return jsonify({
        "status": status,
    })


@app.route('/api/calibrate/start', methods=['POST'])
def api_calibrate_start():
    """Start calibration for a room."""
    global calibration_state
    
    data = request.get_json()
    room_id = data.get('room_id')
    
    if not room_id:
        return jsonify({"success": False, "error": "room_id required"}), 400
    
    # Check if room exists
    room_exists = any(r["id"] == room_id for r in config.ROOMS)
    if not room_exists:
        return jsonify({"success": False, "error": f"Room {room_id} not found"}), 404
    
    if calibration_state["active"]:
        return jsonify({"success": False, "error": "Calibration already in progress"}), 409
    
    # Start calibration in background thread
    calibration_state = {"active": True, "room_id": room_id, "progress": 0, "done": False}
    
    thread = threading.Thread(target=_run_calibration, args=(room_id,), daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": f"Calibration started for {room_id}"})


@app.route('/api/calibrate/progress')
def api_calibrate_progress():
    """Get current calibration progress."""
    return jsonify({
        "active": calibration_state["active"],
        "room_id": calibration_state["room_id"],
        "progress": calibration_state["progress"],
        "done": calibration_state["done"],
    })


@app.route('/api/train', methods=['POST'])
def api_train():
    """Train the ML model from collected fingerprints."""
    try:
        results = train_model(verbose=True)
        
        if results:
            # Reload the model in the predictor
            predictor.load()
            
            return jsonify({
                "success": True,
                "accuracy": results["accuracy"],
                "message": f"Model trained with {results['accuracy']:.1%} accuracy",
            })
        else:
            return jsonify({
                "success": False,
                "error": "Training failed. Need at least 2 calibrated rooms.",
            }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ═══════════════════════════════════════════════════════════════════
#  BACKGROUND WORKERS
# ═══════════════════════════════════════════════════════════════════

def _run_calibration(room_id: str):
    """Run calibration in a background thread."""
    global calibration_state
    
    def progress_callback(progress, scan_count, total_scans):
        calibration_state["progress"] = progress
    
    try:
        print(f"\n  📡 Calibrating room: {room_id}")
        fingerprint = collect_fingerprint(room_id, callback=progress_callback)
        save_fingerprint(fingerprint)
        
        calibration_state["progress"] = 100
        calibration_state["done"] = True
        calibration_state["active"] = False
        
        print(f"  ✅ Calibration complete for {room_id} ({fingerprint['total_scans']} scans)")
    except Exception as e:
        print(f"  ❌ Calibration error: {e}")
        calibration_state["active"] = False
        calibration_state["done"] = True


def _scan_loop():
    """Background loop for continuous WiFi scanning, motion detection, and prediction."""
    global latest_scan, latest_prediction, latest_devices, latest_radar, scan_running
    
    device_scan_counter = 0
    
    while scan_running:
        try:
            # Skip scanning during calibration
            if calibration_state["active"]:
                time.sleep(1)
                continue
            
            # WiFi scan
            networks = scan_wifi()
            latest_scan = {
                "networks": networks,
                "timestamp": time.time(),
            }
            
            # Motion detection (3D Radar)
            radar_result = motion_detector.process_scan(networks)
            latest_radar = radar_result
            
            # Predict room (if model is loaded)
            if predictor.model is not None:
                prediction = predictor.predict(networks)
                latest_prediction = prediction
            
            # Device scan (every N iterations)
            device_scan_counter += 1
            if device_scan_counter >= (config.DEVICE_SCAN_INTERVAL // config.SCAN_INTERVAL):
                device_scan_counter = 0
                try:
                    devices = scan_network_devices()
                    update_known_devices(devices)
                    latest_devices = {
                        "devices": devices,
                        "timestamp": time.time(),
                    }
                except Exception as e:
                    print(f"  [Device Scan Error] {e}")
            
            time.sleep(config.SCAN_INTERVAL)
        
        except Exception as e:
            print(f"  [Scan Loop Error] {e}")
            time.sleep(config.SCAN_INTERVAL)


def start_scanning():
    """Start the background scanning thread."""
    global scan_thread, scan_running
    
    scan_running = True
    scan_thread = threading.Thread(target=_scan_loop, daemon=True)
    scan_thread.start()
    print("  🔄 Background scanning started")


def stop_scanning():
    """Stop the background scanning thread."""
    global scan_running
    scan_running = False
    print("  ⏹️ Background scanning stopped")


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    """Start the WiFi Sense server."""
    print()
    print("  ╔═══════════════════════════════════════════════╗")
    print("  ║     📡 WiFi Sense — 3D Radar System           ║")
    print("  ╠═══════════════════════════════════════════════╣")
    print(f"  ║  Dashboard: http://localhost:{config.SERVER_PORT}            ║")
    print("  ║  Press Ctrl+C to stop                        ║")
    print("  ╚═══════════════════════════════════════════════╝")
    print()
    
    # Try to load existing model
    if is_model_trained():
        if predictor.load():
            print("  ✅ Trained model loaded")
        else:
            print("  ⚠️  Model file found but couldn't load")
    else:
        print("  ℹ️  No trained model. Calibrate rooms first via the dashboard.")
    
    # Start background scanning
    start_scanning()
    
    # Start Flask server
    try:
        app.run(
            host=config.SERVER_HOST,
            port=config.SERVER_PORT,
            debug=False,  # Can't use debug with threading
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\n  Shutting down...")
    finally:
        stop_scanning()


if __name__ == "__main__":
    main()
