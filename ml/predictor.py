"""
Room Predictor Module
======================
Real-time room prediction using the trained ML model.
Takes WiFi scans and predicts which room the user is in.
"""

import time
import json
import os
import sys
from collections import Counter
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scanner.wifi_scanner import scan_wifi, get_rssi_vector
from ml.model import load_model, is_model_trained

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class RoomPredictor:
    """Predicts which room the user is in based on WiFi signals."""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.ap_list = None
        self.prediction_history = []
        self.current_room = None
        self.current_confidence = 0.0
        self.last_room_change = 0
        self.movement_history = []
        self._load_history()
    
    def load(self) -> bool:
        """Load the trained model. Returns True if successful."""
        if not is_model_trained():
            print("[Predictor] No trained model found. Please train first.")
            return False
        
        result = load_model()
        if result is None:
            return False
        
        self.model, self.scaler, self.ap_list = result
        print(f"[Predictor] Model loaded ({len(self.ap_list)} APs)")
        return True
    
    def predict(self, networks: Optional[list[dict]] = None) -> dict:
        """
        Predict the current room based on WiFi signals.
        
        Args:
            networks: Optional pre-scanned network list. If None, performs a new scan.
        
        Returns:
            Dict with: room_id, room_name, confidence, all_probabilities, timestamp
        """
        if self.model is None:
            return self._empty_prediction("Model not loaded")
        
        if not HAS_NUMPY:
            return self._empty_prediction("NumPy not installed")
        
        # Scan WiFi if not provided
        if networks is None:
            networks = scan_wifi()
        
        if not networks:
            return self._empty_prediction("No WiFi networks found")
        
        # Create feature vector
        rssi_vector = get_rssi_vector(networks, self.ap_list)
        features = np.array([list(rssi_vector.values())], dtype=float)
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Predict
        prediction = self.model.predict(features_scaled)[0]
        probabilities = self.model.predict_proba(features_scaled)[0]
        
        # Get class labels and their probabilities
        classes = self.model.classes_
        prob_dict = {cls: float(prob) for cls, prob in zip(classes, probabilities)}
        
        confidence = float(max(probabilities))
        
        # Add to prediction history for majority voting
        self.prediction_history.append(prediction)
        if len(self.prediction_history) > config.PREDICTION_HISTORY_SIZE:
            self.prediction_history.pop(0)
        
        # Majority vote from recent predictions
        if len(self.prediction_history) >= 2:
            vote_counts = Counter(self.prediction_history)
            stable_prediction = vote_counts.most_common(1)[0][0]
        else:
            stable_prediction = prediction
        
        # Check for room change
        now = time.time()
        if stable_prediction != self.current_room:
            if now - self.last_room_change > config.MOVEMENT_COOLDOWN:
                old_room = self.current_room
                self.current_room = stable_prediction
                self.last_room_change = now
                
                # Log movement
                if old_room is not None:
                    self._log_movement(old_room, stable_prediction, confidence)
        
        self.current_confidence = confidence
        
        # Get room name
        room_name = self._get_room_name(stable_prediction)
        room_info = self._get_room_info(stable_prediction)
        
        result = {
            "room_id": stable_prediction,
            "room_name": room_name,
            "room_icon": room_info.get("icon", "📍") if room_info else "📍",
            "room_color": room_info.get("color", "#6366f1") if room_info else "#6366f1",
            "confidence": confidence,
            "raw_prediction": prediction,
            "stable_prediction": stable_prediction,
            "all_probabilities": prob_dict,
            "timestamp": now,
            "num_networks": len(networks),
        }
        
        return result
    
    def _empty_prediction(self, reason: str) -> dict:
        """Return an empty prediction with a reason."""
        return {
            "room_id": None,
            "room_name": "Unknown",
            "room_icon": "❓",
            "room_color": "#666",
            "confidence": 0.0,
            "raw_prediction": None,
            "stable_prediction": None,
            "all_probabilities": {},
            "timestamp": time.time(),
            "num_networks": 0,
            "error": reason,
        }
    
    def _get_room_name(self, room_id: str) -> str:
        """Get room name from config."""
        for room in config.ROOMS:
            if room["id"] == room_id:
                return room["name"]
        return room_id
    
    def _get_room_info(self, room_id: str) -> Optional[dict]:
        """Get full room info from config."""
        for room in config.ROOMS:
            if room["id"] == room_id:
                return room
        return None
    
    def _log_movement(self, from_room: str, to_room: str, confidence: float):
        """Log a room change to movement history."""
        entry = {
            "from_room": from_room,
            "from_name": self._get_room_name(from_room),
            "to_room": to_room,
            "to_name": self._get_room_name(to_room),
            "confidence": confidence,
            "timestamp": time.time(),
        }
        
        self.movement_history.append(entry)
        
        # Trim history
        if len(self.movement_history) > config.MAX_HISTORY_ENTRIES:
            self.movement_history = self.movement_history[-config.MAX_HISTORY_ENTRIES:]
        
        self._save_history()
    
    def _load_history(self):
        """Load movement history from disk."""
        try:
            if os.path.exists(config.HISTORY_FILE):
                with open(config.HISTORY_FILE, "r") as f:
                    self.movement_history = json.load(f)
        except Exception:
            self.movement_history = []
    
    def _save_history(self):
        """Save movement history to disk."""
        try:
            with open(config.HISTORY_FILE, "w") as f:
                json.dump(self.movement_history, f, indent=2)
        except Exception as e:
            print(f"[Predictor] Error saving history: {e}")
    
    def get_movement_history(self, limit: int = 20) -> list[dict]:
        """Get recent movement history."""
        return self.movement_history[-limit:]
    
    def get_status(self) -> dict:
        """Get current prediction status."""
        return {
            "model_loaded": self.model is not None,
            "current_room": self.current_room,
            "current_room_name": self._get_room_name(self.current_room) if self.current_room else "Unknown",
            "current_confidence": self.current_confidence,
            "predictions_made": len(self.prediction_history),
            "movement_count": len(self.movement_history),
        }


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Room Predictor — Real-time Detection Test")
    print("=" * 60)
    
    predictor = RoomPredictor()
    
    if not predictor.load():
        print("\n  ❌ No trained model. Run calibration first.")
        sys.exit(1)
    
    print("\n  🔍 Starting real-time prediction (press Ctrl+C to stop)...\n")
    
    try:
        while True:
            result = predictor.predict()
            
            if result["room_id"]:
                print(f"  {result['room_icon']} Room: {result['room_name']} "
                      f"(confidence: {result['confidence']:.1%}) "
                      f"| {result['num_networks']} networks")
            else:
                print(f"  ❓ {result.get('error', 'Unknown error')}")
            
            time.sleep(config.SCAN_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n  Stopped.")
