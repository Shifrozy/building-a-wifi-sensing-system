"""
Device Tracker Module
=====================
Tracks devices connected to the local network using ARP scanning.
Monitors online/offline status and resolves hostnames.
"""

import subprocess
import re
import json
import time
import socket
import platform
from typing import Optional
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def scan_arp_table() -> list[dict]:
    """
    Read the ARP table to find devices on the local network.
    
    Returns:
        List of dicts with keys: ip, mac, type, interface
    """
    system = platform.system()
    
    try:
        if system == "Windows":
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        else:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        
        if result.returncode != 0:
            return []
        
        return _parse_arp_output(result.stdout, system)
    
    except Exception as e:
        print(f"[Device Tracker] ARP scan error: {e}")
        return []


def _parse_arp_output(output: str, system: str) -> list[dict]:
    """Parse ARP table output."""
    devices = []
    
    if system == "Windows":
        # Windows format: IP address   Physical Address   Type
        for line in output.split("\n"):
            line = line.strip()
            # Match IP, MAC, and type
            match = re.match(
                r"(\d+\.\d+\.\d+\.\d+)\s+([\w-]{17})\s+(\w+)",
                line
            )
            if match:
                ip = match.group(1)
                mac = match.group(2).replace("-", ":").lower()
                entry_type = match.group(3)
                
                # Skip broadcast and multicast addresses
                if mac == "ff:ff:ff:ff:ff:ff" or ip.endswith(".255"):
                    continue
                
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "type": entry_type,
                })
    else:
        # Linux/macOS format varies
        for line in output.split("\n"):
            match = re.search(
                r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([\w:]{17})",
                line
            )
            if match:
                devices.append({
                    "ip": match.group(1),
                    "mac": match.group(2).lower(),
                    "type": "dynamic",
                })
    
    return devices


def resolve_hostname(ip: str) -> Optional[str]:
    """Try to resolve the hostname for an IP address."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return None


def ping_device(ip: str) -> bool:
    """Check if a device is reachable via ping."""
    system = platform.system()
    
    try:
        if system == "Windows":
            result = subprocess.run(
                ["ping", ip, "-n", "1", "-w", "1000"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        else:
            result = subprocess.run(
                ["ping", ip, "-c", "1", "-W", "1"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        
        return result.returncode == 0
    except Exception:
        return False


def get_device_vendor(mac: str) -> str:
    """Get a rough device type based on MAC OUI prefix."""
    oui_map = {
        "00:50:f2": "Microsoft",
        "3c:5a:b4": "Google",
        "f4:f5:d8": "Google",
        "ac:84:c6": "TP-Link",
        "50:c7:bf": "TP-Link",
        "c0:25:e9": "TP-Link",
        "14:cc:20": "TP-Link",
        "e4:5f:01": "Raspberry Pi",
        "b8:27:eb": "Raspberry Pi",
        "dc:a6:32": "Raspberry Pi",
        "a4:c3:f0": "Intel",
        "00:1a:7d": "Intel",
        "00:26:c7": "Intel",
        "34:02:86": "Intel",
        "f8:e4:3b": "Apple",
        "a8:51:5b": "Apple",
        "3c:22:fb": "Apple",
        "88:66:a5": "Apple",
        "a4:83:e7": "Apple",
        "00:1e:c2": "Apple",
        "fc:a1:3e": "Samsung",
        "c0:97:27": "Samsung",
        "8c:f5:a3": "Samsung",
        "44:78:3e": "Samsung",
        "e0:db:55": "Huawei",
        "78:f5:57": "Huawei",
        "5c:c3:07": "Huawei",
        "30:d1:6b": "Xiaomi",
        "64:cc:2e": "Xiaomi",
        "28:6c:07": "Xiaomi",
        "60:ab:67": "Xiaomi",
        "20:34:fb": "Oppo",
        "b4:a9:fc": "Oppo",
        "2c:4d:54": "Vivo",
        "d8:b1:22": "Realme",
    }
    
    prefix = mac[:8].lower()
    return oui_map.get(prefix, "Unknown")


def scan_network_devices() -> list[dict]:
    """
    Full network scan: ARP table + hostname resolution + vendor identification.
    
    Returns:
        List of device dicts with: ip, mac, hostname, vendor, online, last_seen
    """
    arp_devices = scan_arp_table()
    devices = []
    
    for dev in arp_devices:
        ip = dev["ip"]
        mac = dev["mac"]
        
        # Only include devices on our subnet
        if not ip.startswith(config.NETWORK_SUBNET):
            continue
        
        hostname = resolve_hostname(ip)
        vendor = get_device_vendor(mac)
        
        device_info = {
            "ip": ip,
            "mac": mac,
            "hostname": hostname or f"device-{mac[-5:].replace(':', '')}",
            "vendor": vendor,
            "online": True,
            "last_seen": time.time(),
            "type": _guess_device_type(hostname, vendor),
        }
        
        devices.append(device_info)
    
    return devices


def _guess_device_type(hostname: Optional[str], vendor: str) -> str:
    """Guess the device type based on hostname and vendor."""
    if hostname:
        hostname_lower = hostname.lower()
        if any(kw in hostname_lower for kw in ["iphone", "ipad", "macbook", "android", "galaxy", "pixel", "huawei", "xiaomi", "redmi", "oppo", "vivo", "realme"]):
            return "phone"
        if any(kw in hostname_lower for kw in ["laptop", "desktop", "pc", "macbook", "surface"]):
            return "computer"
        if any(kw in hostname_lower for kw in ["tv", "chromecast", "firestick", "roku"]):
            return "tv"
        if any(kw in hostname_lower for kw in ["printer", "canon", "hp", "epson"]):
            return "printer"
    
    if vendor in ["Apple", "Samsung", "Huawei", "Xiaomi", "Oppo", "Vivo", "Realme"]:
        return "phone"
    if vendor in ["Intel", "Microsoft"]:
        return "computer"
    if vendor in ["Google"]:
        return "smart_device"
    if vendor in ["TP-Link"]:
        return "router"
    
    return "unknown"


def load_known_devices() -> dict:
    """Load known devices from file."""
    try:
        if os.path.exists(config.KNOWN_DEVICES_FILE):
            with open(config.KNOWN_DEVICES_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_known_devices(devices: dict):
    """Save known devices to file."""
    try:
        with open(config.KNOWN_DEVICES_FILE, "w") as f:
            json.dump(devices, f, indent=2)
    except Exception as e:
        print(f"[Device Tracker] Error saving devices: {e}")


def update_known_devices(current_devices: list[dict]) -> dict:
    """
    Update known devices database with current scan results.
    Tracks when devices were first/last seen.
    """
    known = load_known_devices()
    
    for dev in current_devices:
        mac = dev["mac"]
        if mac in known:
            known[mac]["last_seen"] = dev["last_seen"]
            known[mac]["online"] = True
            known[mac]["ip"] = dev["ip"]
            if dev.get("hostname"):
                known[mac]["hostname"] = dev["hostname"]
        else:
            dev["first_seen"] = dev["last_seen"]
            known[mac] = dev
    
    # Mark devices not in current scan as offline
    current_macs = {dev["mac"] for dev in current_devices}
    for mac in known:
        if mac not in current_macs:
            known[mac]["online"] = False
    
    save_known_devices(known)
    return known


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Device Tracker — Scanning network devices...")
    print("=" * 60)
    
    devices = scan_network_devices()
    
    if not devices:
        print("\n  ❌ No devices found on the network.")
    else:
        print(f"\n  ✅ Found {len(devices)} device(s):\n")
        for i, dev in enumerate(devices, 1):
            icon = {"phone": "📱", "computer": "💻", "tv": "📺", "printer": "🖨️",
                    "router": "🌐", "smart_device": "🏠", "unknown": "❓"}.get(dev["type"], "❓")
            print(f"  {i}. {icon}  {dev['hostname']}")
            print(f"     IP: {dev['ip']}  |  MAC: {dev['mac']}")
            print(f"     Vendor: {dev['vendor']}  |  Type: {dev['type']}")
            print()
