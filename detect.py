"""
WiFi Sense — Main Detection Script
====================================
Entry point to start the detection system.
Launches the Flask server + background scanning + opens dashboard.

Usage:
    python detect.py              # Start with dashboard
    python detect.py --no-browser # Don't open browser
    python detect.py --cli        # CLI-only mode (no dashboard)
    python detect.py --port 8080  # Custom port
"""

import os
import sys
import time
import argparse
import webbrowser
import threading

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from ml.model import is_model_trained


def print_banner():
    """Print the startup banner."""
    print()
    print("  ╔═══════════════════════════════════════════════════════╗")
    print("  ║                                                       ║")
    print("  ║     📡  WiFi Sense — Room Detection System            ║")
    print("  ║     ─────────────────────────────────────────          ║")
    print("  ║     WiFi signals se pata lagao kaun kahan hai!        ║")
    print("  ║                                                       ║")
    print("  ╚═══════════════════════════════════════════════════════╝")
    print()


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import flask
    except ImportError:
        missing.append("flask")
    
    try:
        import flask_cors
    except ImportError:
        missing.append("flask-cors")
    
    try:
        import sklearn
    except ImportError:
        missing.append("scikit-learn")
    
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    
    if missing:
        print("  ❌ Missing dependencies:")
        for pkg in missing:
            print(f"     • {pkg}")
        print()
        print(f"  Install karo: pip install {' '.join(missing)}")
        print("  Ya: pip install -r requirements.txt")
        return False
    
    return True


def run_cli_mode():
    """Run detection in CLI-only mode (no dashboard)."""
    from ml.predictor import RoomPredictor
    from scanner.wifi_scanner import scan_wifi
    
    predictor = RoomPredictor()
    
    if not predictor.load():
        print("  ❌ No trained model. Run 'python calibrate.py' first.")
        sys.exit(1)
    
    print("  🔍 CLI Detection Mode — Press Ctrl+C to stop")
    print("  " + "─" * 50)
    print()
    
    try:
        while True:
            result = predictor.predict()
            
            now = time.strftime("%H:%M:%S")
            
            if result["room_id"]:
                confidence_bar = "█" * int(result["confidence"] * 10) + "░" * (10 - int(result["confidence"] * 10))
                
                print(f"  [{now}] {result['room_icon']} {result['room_name']:15} "
                      f"[{confidence_bar}] {result['confidence']:.0%} "
                      f"| {result['num_networks']} APs")
            else:
                print(f"  [{now}] ❓ {result.get('error', 'Unknown')}")
            
            time.sleep(config.SCAN_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n  Stopped. 👋")


def main():
    parser = argparse.ArgumentParser(description="WiFi Sense — Start the detection system")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--cli", action="store_true", help="CLI-only mode (no web dashboard)")
    parser.add_argument("--port", type=int, default=config.SERVER_PORT, help=f"Server port (default: {config.SERVER_PORT})")
    
    args = parser.parse_args()
    
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("  ✅ All dependencies OK")
    
    # Check model status
    if is_model_trained():
        print("  ✅ Trained model found")
    else:
        print("  ⚠️  No trained model. Rooms ko pehle calibrate karo.")
        print("     Run: python calibrate.py")
        print("     Ya dashboard se calibrate karo (⚙️ button)")
        print()
    
    # Update port if specified
    if args.port != config.SERVER_PORT:
        config.SERVER_PORT = args.port
    
    if args.cli:
        run_cli_mode()
        return
    
    # Open browser after short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(2)
            url = f"http://localhost:{config.SERVER_PORT}"
            print(f"\n  🌐 Opening dashboard: {url}")
            webbrowser.open(url)
        
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()
    
    # Start server
    print(f"  🚀 Starting server on port {config.SERVER_PORT}...")
    print()
    
    from server import main as server_main
    server_main()


if __name__ == "__main__":
    main()
