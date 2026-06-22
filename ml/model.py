"""
ML Model Module
================
Random Forest classifier for WiFi-based room prediction.
Trains on RSSI fingerprints and predicts which room a person is in.
"""

import json
import os
import pickle
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from ml.fingerprint import prepare_training_data, load_all_fingerprints

try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import classification_report, confusion_matrix
    HAS_ML = True
except ImportError:
    HAS_ML = False
    print("[ML Model] Warning: scikit-learn or numpy not installed. Run: pip install scikit-learn numpy")


def train_model(verbose: bool = True) -> Optional[dict]:
    """
    Train a Random Forest classifier on collected fingerprints.
    
    Args:
        verbose: If True, print training details
    
    Returns:
        Dict with training results (accuracy, report) or None on failure
    """
    if not HAS_ML:
        print("❌ scikit-learn not installed. Run: pip install scikit-learn numpy")
        return None
    
    # Prepare data
    X, y, ap_list = prepare_training_data()
    
    if not X:
        print("❌ No training data found. Please calibrate rooms first.")
        return None
    
    if len(set(y)) < 2:
        print("❌ Need at least 2 calibrated rooms to train. Please calibrate more rooms.")
        return None
    
    X = np.array(X, dtype=float)
    y = np.array(y)
    
    if verbose:
        print(f"\n  📊 Training Data:")
        print(f"     Samples: {len(X)}")
        print(f"     Features (APs): {len(ap_list)}")
        print(f"     Classes (Rooms): {len(set(y))}")
        
        # Samples per room
        for room_id in sorted(set(y)):
            count = sum(1 for label in y if label == room_id)
            room_name = next((r["name"] for r in config.ROOMS if r["id"] == room_id), room_id)
            print(f"       • {room_name}: {count} samples")
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train Random Forest
    model = RandomForestClassifier(**config.MODEL_PARAMS)
    model.fit(X_scaled, y)
    
    # Cross-validation
    results = {"accuracy": 0, "report": "", "confusion_matrix": None}
    
    n_splits = min(3, min(sum(1 for label in y if label == room_id) for room_id in set(y)))
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="accuracy")
        results["accuracy"] = float(np.mean(scores))
        
        if verbose:
            print(f"\n  🎯 Cross-Validation Accuracy: {results['accuracy']:.1%}")
            print(f"     Std: ±{float(np.std(scores)):.1%}")
    else:
        # Not enough samples for CV, just report training accuracy
        train_pred = model.predict(X_scaled)
        results["accuracy"] = float(np.mean(train_pred == y))
        if verbose:
            print(f"\n  🎯 Training Accuracy: {results['accuracy']:.1%}")
            print(f"     (Not enough samples for cross-validation)")
    
    # Feature importance
    if verbose:
        importances = model.feature_importances_
        top_indices = np.argsort(importances)[-5:][::-1]
        print(f"\n  📡 Top 5 Most Important APs:")
        for idx in top_indices:
            print(f"     • {ap_list[idx]}: {importances[idx]:.3f}")
    
    # Save model, scaler, and AP list
    _save_model(model, scaler, ap_list)
    
    if verbose:
        print(f"\n  ✅ Model saved successfully!")
    
    return results


def _save_model(model, scaler, ap_list: list[str]):
    """Save trained model, scaler, and AP list to disk."""
    with open(config.MODEL_FILE, "wb") as f:
        pickle.dump(model, f)
    
    with open(config.SCALER_FILE, "wb") as f:
        pickle.dump(scaler, f)
    
    with open(config.AP_LIST_FILE, "w") as f:
        json.dump(ap_list, f, indent=2)


def load_model() -> Optional[tuple]:
    """
    Load trained model from disk.
    
    Returns:
        Tuple of (model, scaler, ap_list) or None if not found
    """
    if not all(os.path.exists(f) for f in [config.MODEL_FILE, config.SCALER_FILE, config.AP_LIST_FILE]):
        return None
    
    try:
        with open(config.MODEL_FILE, "rb") as f:
            model = pickle.load(f)
        
        with open(config.SCALER_FILE, "rb") as f:
            scaler = pickle.load(f)
        
        with open(config.AP_LIST_FILE, "r") as f:
            ap_list = json.load(f)
        
        return model, scaler, ap_list
    except Exception as e:
        print(f"[ML Model] Error loading model: {e}")
        return None


def is_model_trained() -> bool:
    """Check if a trained model exists."""
    return all(os.path.exists(f) for f in [config.MODEL_FILE, config.SCALER_FILE, config.AP_LIST_FILE])


def delete_model():
    """Delete the trained model files."""
    for f in [config.MODEL_FILE, config.SCALER_FILE, config.AP_LIST_FILE]:
        if os.path.exists(f):
            os.remove(f)


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ML Model — Training WiFi Room Classifier")
    print("=" * 60)
    
    if is_model_trained():
        print("\n  ℹ️  Existing model found. Retraining...")
    
    results = train_model(verbose=True)
    
    if results:
        print(f"\n  🎉 Model trained with {results['accuracy']:.1%} accuracy!")
    else:
        print("\n  ❌ Training failed. Please calibrate rooms first.")
