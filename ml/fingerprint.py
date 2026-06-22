"""
WiFi Fingerprint Module
========================
Collects and manages WiFi RSSI fingerprints for each room.
A fingerprint is a set of RSSI readings from all visible access points,
captured at a specific location (room).
"""

import json
import os
import time
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scanner.wifi_scanner import scan_wifi, scan_wifi_averaged, get_rssi_vector


def collect_fingerprint(room_id: str, duration: int = None, callback=None) -> dict:
    """
    Collect WiFi fingerprints for a specific room.
    
    Performs multiple scans over the specified duration and stores
    all RSSI vectors as training data for that room.
    
    Args:
        room_id: The room identifier (e.g., "room_1")
        duration: How long to collect (seconds), defaults to config.CALIBRATION_DURATION
        callback: Optional function called with (progress_percent, scan_count, total_scans)
    
    Returns:
        Dict with fingerprint data including all scans and metadata
    """
    if duration is None:
        duration = config.CALIBRATION_DURATION
    
    num_scans = config.CALIBRATION_SCANS
    interval = duration / num_scans
    
    fingerprint = {
        "room_id": room_id,
        "timestamp": time.time(),
        "duration": duration,
        "scans": [],
        "ap_list": set(),
    }
    
    for i in range(num_scans):
        # Perform an averaged scan for stability
        networks = scan_wifi_averaged(num_scans=2, interval=0.3)
        rssi_vector = get_rssi_vector(networks)
        
        if rssi_vector:
            fingerprint["scans"].append({
                "scan_index": i,
                "timestamp": time.time(),
                "rssi": rssi_vector,
                "num_aps": len(rssi_vector),
            })
            fingerprint["ap_list"].update(rssi_vector.keys())
        
        # Report progress
        progress = int(((i + 1) / num_scans) * 100)
        if callback:
            callback(progress, i + 1, num_scans)
        
        # Wait before next scan (except for last)
        if i < num_scans - 1:
            time.sleep(max(0, interval - 0.6))  # subtract scan time
    
    # Convert set to list for JSON serialization
    fingerprint["ap_list"] = list(fingerprint["ap_list"])
    fingerprint["total_scans"] = len(fingerprint["scans"])
    
    return fingerprint


def save_fingerprint(fingerprint: dict):
    """Save a fingerprint to disk."""
    room_id = fingerprint["room_id"]
    filepath = os.path.join(config.FINGERPRINT_DIR, f"{room_id}.json")
    
    # Load existing fingerprints for this room (if any)
    existing = load_fingerprint(room_id)
    
    if existing:
        # Append new scans to existing data
        existing["scans"].extend(fingerprint["scans"])
        existing["ap_list"] = list(set(existing["ap_list"] + fingerprint["ap_list"]))
        existing["total_scans"] = len(existing["scans"])
        existing["last_updated"] = time.time()
        data = existing
    else:
        fingerprint["last_updated"] = time.time()
        data = fingerprint
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"  💾 Fingerprint saved: {filepath} ({data['total_scans']} scans)")


def load_fingerprint(room_id: str) -> Optional[dict]:
    """Load a fingerprint from disk."""
    filepath = os.path.join(config.FINGERPRINT_DIR, f"{room_id}.json")
    
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    
    return None


def load_all_fingerprints() -> dict[str, dict]:
    """Load all room fingerprints."""
    fingerprints = {}
    
    for room in config.ROOMS:
        fp = load_fingerprint(room["id"])
        if fp:
            fingerprints[room["id"]] = fp
    
    return fingerprints


def delete_fingerprint(room_id: str) -> bool:
    """Delete a room's fingerprint data."""
    filepath = os.path.join(config.FINGERPRINT_DIR, f"{room_id}.json")
    
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def delete_all_fingerprints():
    """Delete all fingerprint data."""
    for room in config.ROOMS:
        delete_fingerprint(room["id"])


def get_calibration_status() -> dict:
    """Get the calibration status for all rooms."""
    status = {}
    
    for room in config.ROOMS:
        fp = load_fingerprint(room["id"])
        if fp:
            status[room["id"]] = {
                "calibrated": True,
                "total_scans": fp.get("total_scans", 0),
                "num_aps": len(fp.get("ap_list", [])),
                "last_updated": fp.get("last_updated"),
            }
        else:
            status[room["id"]] = {
                "calibrated": False,
                "total_scans": 0,
                "num_aps": 0,
                "last_updated": None,
            }
    
    return status


def get_all_ap_list() -> list[str]:
    """Get a combined list of all unique APs seen across all rooms."""
    all_aps = set()
    
    fingerprints = load_all_fingerprints()
    for fp in fingerprints.values():
        all_aps.update(fp.get("ap_list", []))
    
    return sorted(list(all_aps))


def prepare_training_data(fingerprints: Optional[dict] = None) -> tuple:
    """
    Prepare training data from fingerprints for the ML model.
    
    Returns:
        Tuple of (X, y, ap_list) where:
        - X: list of RSSI vectors (each vector is a list of RSSI values)
        - y: list of room IDs
        - ap_list: ordered list of AP BSSIDs (column headers for X)
    """
    if fingerprints is None:
        fingerprints = load_all_fingerprints()
    
    if not fingerprints:
        return [], [], []
    
    # Get combined AP list
    ap_list = get_all_ap_list()
    
    X = []
    y = []
    
    for room_id, fp in fingerprints.items():
        for scan in fp.get("scans", []):
            rssi = scan.get("rssi", {})
            # Create feature vector aligned with ap_list
            vector = [rssi.get(ap, config.MIN_RSSI) for ap in ap_list]
            X.append(vector)
            y.append(room_id)
    
    return X, y, ap_list


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  WiFi Fingerprint — Calibration Status")
    print("=" * 60)
    
    status = get_calibration_status()
    
    for room in config.ROOMS:
        rid = room["id"]
        s = status[rid]
        icon = "✅" if s["calibrated"] else "❌"
        print(f"\n  {icon} {room['icon']} {room['name']} ({rid})")
        if s["calibrated"]:
            print(f"     Scans: {s['total_scans']}  |  APs: {s['num_aps']}")
        else:
            print(f"     Not calibrated yet")
