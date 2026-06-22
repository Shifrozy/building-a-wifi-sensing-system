"""
WiFi Sense — Room Calibration CLI Tool
========================================
Interactive tool to calibrate each room by collecting WiFi fingerprints.
Run this first before using the detection system.

Usage:
    python calibrate.py           # Interactive calibration
    python calibrate.py --room 1  # Calibrate specific room
    python calibrate.py --reset   # Delete all calibration data
    python calibrate.py --status  # Show calibration status
    python calibrate.py --train   # Train model after calibration
"""

import os
import sys
import time
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from scanner.wifi_scanner import scan_wifi
from ml.fingerprint import (
    collect_fingerprint, save_fingerprint, get_calibration_status,
    delete_all_fingerprints, delete_fingerprint
)
from ml.model import train_model, is_model_trained


def print_banner():
    """Print the calibration banner."""
    print()
    print("  ╔═══════════════════════════════════════════════╗")
    print("  ║     ⚙️  WiFi Sense — Room Calibration         ║")
    print("  ╚═══════════════════════════════════════════════╝")
    print()


def print_status():
    """Print calibration status for all rooms."""
    status = get_calibration_status()
    
    print("  Room Calibration Status:")
    print("  " + "─" * 45)
    
    all_calibrated = True
    for room in config.ROOMS:
        rid = room["id"]
        s = status[rid]
        icon = "✅" if s["calibrated"] else "❌"
        
        if not s["calibrated"]:
            all_calibrated = False
        
        detail = f'{s["total_scans"]} scans, {s["num_aps"]} APs' if s["calibrated"] else "Not calibrated"
        print(f"  {icon} {room['icon']} {room['name']:15} | {detail}")
    
    print("  " + "─" * 45)
    
    model_status = "✅ Trained" if is_model_trained() else "❌ Not trained"
    print(f"  Model: {model_status}")
    print()
    
    return all_calibrated


def calibrate_room(room_id: str, room_name: str):
    """Calibrate a single room."""
    print(f"\n  📡 Calibrating: {room_name}")
    print(f"  ───────────────────────────────────────")
    print(f"  ➡️  {room_name} mein jao aur wahan raho.")
    print(f"  ➡️  {config.CALIBRATION_DURATION} seconds tak WiFi signals record honge.")
    print()
    
    input("  Enter dabo jab tayyar ho... ")
    print()
    
    # Quick pre-check
    networks = scan_wifi()
    if not networks:
        print("  ❌ Koi WiFi network nahi mili! WiFi check karo.")
        return False
    
    print(f"  📶 {len(networks)} networks detected. Scanning shuru...")
    print()
    
    def progress_callback(progress, scan_count, total_scans):
        bar_len = 30
        filled = int(bar_len * progress / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(f"\r  [{bar}] {progress:3d}% ({scan_count}/{total_scans} scans)")
        sys.stdout.flush()
    
    fingerprint = collect_fingerprint(room_id, callback=progress_callback)
    
    if fingerprint["total_scans"] == 0:
        print("\n  ❌ Koi scan data nahi mila. Dobara try karo.")
        return False
    
    save_fingerprint(fingerprint)
    
    print(f"\n\n  ✅ {room_name} calibrate ho gaya!")
    print(f"     Scans: {fingerprint['total_scans']} | APs: {len(fingerprint['ap_list'])}")
    
    return True


def interactive_calibration():
    """Interactive calibration for all rooms."""
    print("  Ye tool har room mein WiFi signals record karega.")
    print("  Har room ke liye alag se data collect hoga.")
    print()
    
    # Show available rooms
    for i, room in enumerate(config.ROOMS, 1):
        print(f"  {i}. {room['icon']} {room['name']}")
    
    print()
    print("  Kya tum sab rooms calibrate karna chahte ho? (Y/n): ", end="")
    choice = input().strip().lower()
    
    if choice in ("", "y", "yes", "haan", "ha"):
        # Calibrate all rooms
        for room in config.ROOMS:
            success = calibrate_room(room["id"], room["name"])
            if not success:
                print(f"\n  ⚠️  {room['name']} skip ho gaya.")
            print()
    else:
        # Let user pick a room
        print("  Room number dalo (1-{}): ".format(len(config.ROOMS)), end="")
        try:
            num = int(input().strip())
            if 1 <= num <= len(config.ROOMS):
                room = config.ROOMS[num - 1]
                calibrate_room(room["id"], room["name"])
            else:
                print("  ❌ Invalid room number.")
                return
        except (ValueError, EOFError):
            print("  ❌ Invalid input.")
            return
    
    print()
    
    # Check if we can train
    status = get_calibration_status()
    calibrated_count = sum(1 for s in status.values() if s["calibrated"])
    
    if calibrated_count >= 2:
        print("  🧠 Model train karna chahte ho? (Y/n): ", end="")
        train_choice = input().strip().lower()
        
        if train_choice in ("", "y", "yes", "haan", "ha"):
            print("\n  Training model...")
            results = train_model(verbose=True)
            
            if results:
                print(f"\n  🎉 Model trained! Accuracy: {results['accuracy']:.1%}")
                print(f"  Ab 'python detect.py' run karo detection shuru karne ke liye!")
            else:
                print("\n  ❌ Training failed.")
    else:
        print(f"  ⚠️  Kam se kam 2 rooms calibrate karo model train karne ke liye.")
        print(f"     Abhi {calibrated_count} room(s) calibrated hain.")


def main():
    parser = argparse.ArgumentParser(description="WiFi Sense — Room Calibration Tool")
    parser.add_argument("--room", type=int, help="Calibrate specific room (1-{})".format(len(config.ROOMS)))
    parser.add_argument("--reset", action="store_true", help="Delete all calibration data")
    parser.add_argument("--status", action="store_true", help="Show calibration status")
    parser.add_argument("--train", action="store_true", help="Train model from existing data")
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.status:
        print_status()
        return
    
    if args.reset:
        print("  ⚠️  Sab calibration data delete ho jayega!")
        print("  Confirm karo (y/N): ", end="")
        if input().strip().lower() in ("y", "yes"):
            delete_all_fingerprints()
            print("  ✅ Sab calibration data delete ho gaya.")
        else:
            print("  Cancelled.")
        return
    
    if args.train:
        print("  🧠 Training model from existing calibration data...")
        results = train_model(verbose=True)
        if results:
            print(f"\n  🎉 Done! Accuracy: {results['accuracy']:.1%}")
        else:
            print("\n  ❌ Failed. Calibrate rooms first.")
        return
    
    if args.room:
        if 1 <= args.room <= len(config.ROOMS):
            room = config.ROOMS[args.room - 1]
            calibrate_room(room["id"], room["name"])
        else:
            print(f"  ❌ Invalid room number. Use 1-{len(config.ROOMS)}")
        return
    
    # Show status first
    print_status()
    
    # Interactive mode
    interactive_calibration()


if __name__ == "__main__":
    main()
