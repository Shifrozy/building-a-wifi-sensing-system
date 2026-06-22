"""
Network Scan — Simple Connectivity Test
=========================================
Quick utility to test if the WiFi router is reachable via ping.
This is a basic network check, not part of the main sensing system.

Usage:
    python network_scan.py
"""

import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
    router_ip = config.ROUTER_IP
except ImportError:
    router_ip = "192.168.100.1"


def ping_router(ip: str = None) -> bool:
    """Ping the router to check connectivity."""
    if ip is None:
        ip = router_ip
    
    result = subprocess.run(
        ["ping", ip, "-n", "1"],
        capture_output=True,
        text=True
    )
    
    return "Reply" in result.stdout


if __name__ == "__main__":
    print(f"  📡 Pinging router at {router_ip}...")
    
    if ping_router():
        print(f"  ✅ Router is reachable!")
    else:
        print(f"  ❌ Router not reachable. Check your WiFi connection.")