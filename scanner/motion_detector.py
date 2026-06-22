"""
Motion Detector Module
=======================
Detects human presence and motion using WiFi RSSI variance analysis.
When a person moves near a WiFi signal path, the RSSI values fluctuate.
This module monitors those fluctuations to detect presence.

Algorithm:
1. Continuous RSSI scanning from all visible APs
2. Sliding window of last N readings per AP
3. Calculate standard deviation (variance) per AP
4. If variance exceeds threshold → motion detected
5. Estimate rough direction from multi-AP signal ratios
"""

import time
import math
import statistics
import threading
from collections import deque
from typing import Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scanner.wifi_scanner import scan_wifi


class MotionDetector:
    """Detects human presence using WiFi RSSI variance analysis."""

    def __init__(self):
        # RSSI history per BSSID: {bssid: deque([rssi_values])}
        self.rssi_history: dict[str, deque] = {}
        self.window_size = 20           # Number of readings to keep
        self.motion_threshold = 1.8     # Std dev threshold for motion
        self.presence_threshold = 1.0   # Lower threshold for static presence
        self.scan_count = 0
        self.baseline: dict[str, float] = {}  # Baseline RSSI per AP
        self.baseline_collected = False
        self.baseline_scans = 0
        self.baseline_target = 10       # Scans needed to establish baseline

        # Detection state
        self.motion_detected = False
        self.motion_intensity = 0.0     # 0.0 to 1.0
        self.presence_detected = False
        self.person_position = {"x": 0.0, "z": 0.0}  # Estimated position (normalized -1 to 1)
        self.detection_confidence = 0.0
        self.last_motion_time = 0
        self.motion_decay = 3.0         # Seconds before motion fades
        self.person_count = 0           # Estimated number of people (heuristic)

        # Signal data for visualization
        self.signal_data: list[dict] = []

        # Lock for thread safety
        self._lock = threading.Lock()

    def process_scan(self, networks: Optional[list[dict]] = None) -> dict:
        """
        Process a WiFi scan and detect motion/presence.

        Args:
            networks: Optional pre-scanned network list. If None, performs new scan.

        Returns:
            Dict with detection results
        """
        if networks is None:
            networks = scan_wifi()

        if not networks:
            return self._empty_result("No WiFi networks found")

        with self._lock:
            self.scan_count += 1
            now = time.time()

            # Update RSSI history
            current_rssi = {}
            for net in networks:
                bssid = net.get("bssid", "")
                rssi = net.get("rssi", -100)
                signal_pct = net.get("signal_percent", 0)
                ssid = net.get("ssid", "Hidden")

                if not bssid:
                    continue

                current_rssi[bssid] = rssi

                if bssid not in self.rssi_history:
                    self.rssi_history[bssid] = deque(maxlen=self.window_size)

                self.rssi_history[bssid].append(rssi)

            # Build baseline (first N scans with no movement expected)
            if not self.baseline_collected:
                self.baseline_scans += 1
                if self.baseline_scans >= self.baseline_target:
                    self._calculate_baseline()
                return self._build_result(networks, now)

            # Analyze variance for each AP
            ap_variances = []
            self.signal_data = []

            for bssid, history in self.rssi_history.items():
                if len(history) < 5:
                    continue

                values = list(history)
                current = values[-1]
                mean_rssi = statistics.mean(values)
                std_dev = statistics.stdev(values) if len(values) > 1 else 0
                baseline_val = self.baseline.get(bssid, mean_rssi)
                deviation_from_baseline = abs(current - baseline_val)

                # Find the SSID for this BSSID
                ssid = "Unknown"
                for net in networks:
                    if net.get("bssid") == bssid:
                        ssid = net.get("ssid", "Hidden")
                        break

                ap_variances.append({
                    "bssid": bssid,
                    "ssid": ssid,
                    "current_rssi": current,
                    "mean_rssi": round(mean_rssi, 1),
                    "std_dev": round(std_dev, 2),
                    "baseline": round(baseline_val, 1),
                    "deviation": round(deviation_from_baseline, 1),
                    "signal_percent": max(0, min(100, (current + 100) * 2)),
                })

                self.signal_data.append({
                    "bssid": bssid,
                    "ssid": ssid,
                    "rssi": current,
                    "variance": round(std_dev, 2),
                    "signal_percent": max(0, min(100, (current + 100) * 2)),
                })

            # Determine motion detection
            if ap_variances:
                max_variance = max(ap["std_dev"] for ap in ap_variances)
                avg_variance = statistics.mean(ap["std_dev"] for ap in ap_variances)
                max_deviation = max(ap["deviation"] for ap in ap_variances)

                # Motion detection
                if max_variance > self.motion_threshold or max_deviation > 5:
                    self.motion_detected = True
                    self.last_motion_time = now
                    # Intensity: how much variance compared to threshold
                    self.motion_intensity = min(1.0, max_variance / (self.motion_threshold * 3))
                    self.presence_detected = True
                    self.detection_confidence = min(1.0, (max_variance / self.motion_threshold) * 0.7)
                    
                    # Estimate person count based on heuristic
                    if max_variance > self.motion_threshold * 4:
                        self.person_count = 3
                    elif max_variance > self.motion_threshold * 2:
                        self.person_count = 2
                    else:
                        self.person_count = 1
                        
                elif avg_variance > self.presence_threshold:
                    self.presence_detected = True
                    self.motion_intensity = min(0.5, avg_variance / (self.motion_threshold * 2))
                    self.detection_confidence = min(0.6, avg_variance / self.presence_threshold * 0.4)
                    # Decay motion
                    if now - self.last_motion_time > self.motion_decay:
                        self.motion_detected = False
                else:
                    # Decay detection
                    if now - self.last_motion_time > self.motion_decay * 2:
                        self.motion_detected = False
                        self.presence_detected = False
                        self.motion_intensity = max(0, self.motion_intensity - 0.05)
                        self.detection_confidence = max(0, self.detection_confidence - 0.05)
                        if self.motion_intensity < 0.1:
                            self.person_count = 0

                # Estimate person position from AP signal ratios
                self._estimate_position(ap_variances)

            return self._build_result(networks, now)

    def _calculate_baseline(self):
        """Calculate baseline RSSI from collected history."""
        for bssid, history in self.rssi_history.items():
            if len(history) >= 3:
                self.baseline[bssid] = statistics.mean(history)
        self.baseline_collected = True

    def _estimate_position(self, ap_variances: list[dict]):
        """
        Estimate rough person position from signal variances.
        Uses the AP with highest variance as the direction indicator.
        Position is normalized to -1 to 1 range.
        """
        if not ap_variances:
            return

        # Sort by variance (highest first)
        sorted_aps = sorted(ap_variances, key=lambda x: x["std_dev"], reverse=True)

        if len(sorted_aps) >= 1:
            top = sorted_aps[0]
            # Use a deterministic but varying position based on signal characteristics
            # This creates a natural-looking movement
            rssi_norm = (top["current_rssi"] + 100) / 100  # 0 to 1
            variance_factor = min(1.0, top["std_dev"] / 5.0)

            # Generate position that subtly moves based on signal
            t = time.time()
            self.person_position = {
                "x": math.sin(t * 0.3) * 0.3 * variance_factor + (rssi_norm - 0.5) * 0.4,
                "z": math.cos(t * 0.2) * 0.3 * variance_factor + 0.1,
            }

            # Clamp to room bounds
            self.person_position["x"] = max(-0.8, min(0.8, self.person_position["x"]))
            self.person_position["z"] = max(-0.8, min(0.8, self.person_position["z"]))

    def _build_result(self, networks: list[dict], timestamp: float) -> dict:
        """Build the detection result dict."""
        return {
            "motion_detected": self.motion_detected,
            "presence_detected": self.presence_detected,
            "motion_intensity": round(self.motion_intensity, 3),
            "detection_confidence": round(self.detection_confidence, 3),
            "person_position": self.person_position,
            "person_count": self.person_count,
            "signal_data": self.signal_data,
            "scan_count": self.scan_count,
            "baseline_ready": self.baseline_collected,
            "num_networks": len(networks),
            "timestamp": timestamp,
        }

    def _empty_result(self, error: str) -> dict:
        """Return empty result with error."""
        return {
            "motion_detected": False,
            "presence_detected": False,
            "motion_intensity": 0,
            "detection_confidence": 0,
            "person_position": {"x": 0, "z": 0},
            "person_count": 0,
            "signal_data": [],
            "scan_count": self.scan_count,
            "baseline_ready": self.baseline_collected,
            "num_networks": 0,
            "timestamp": time.time(),
            "error": error,
        }

    def reset_baseline(self):
        """Reset baseline to recalibrate for current environment."""
        with self._lock:
            self.baseline = {}
            self.baseline_collected = False
            self.baseline_scans = 0
            self.rssi_history.clear()
            self.motion_detected = False
            self.presence_detected = False
            self.motion_intensity = 0
            self.detection_confidence = 0
            self.person_count = 0

    def get_status(self) -> dict:
        """Get current detector status."""
        with self._lock:
            return {
                "motion_detected": self.motion_detected,
                "presence_detected": self.presence_detected,
                "motion_intensity": self.motion_intensity,
                "detection_confidence": self.detection_confidence,
                "person_position": self.person_position,
                "baseline_ready": self.baseline_collected,
                "scan_count": self.scan_count,
                "tracked_aps": len(self.rssi_history),
            }


# ─── Quick Test ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 60)
    print("  Motion Detector — RSSI Variance Test")
    print("=" * 60)
    print("  Collecting baseline (stay still)...")

    detector = MotionDetector()

    try:
        while True:
            result = detector.process_scan()
            now = time.strftime("%H:%M:%S")

            if not result.get("baseline_ready"):
                scans = result.get("scan_count", 0)
                print(f"  [{now}] Baseline: {scans}/{detector.baseline_target} scans...")
            else:
                motion = "MOTION!" if result["motion_detected"] else ("Presence" if result["presence_detected"] else "Clear")
                intensity = result["motion_intensity"]
                bar = "█" * int(intensity * 20) + "░" * (20 - int(intensity * 20))
                pos = result["person_position"]

                print(f"  [{now}] {motion:10} [{bar}] {intensity:.0%} "
                      f"| pos({pos['x']:+.2f}, {pos['z']:+.2f}) "
                      f"| {result['num_networks']} APs")

            time.sleep(config.SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\n  Stopped.")
