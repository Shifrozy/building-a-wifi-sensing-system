"""
WiFi Scanner Module
====================
Scans nearby WiFi networks and extracts RSSI (signal strength) data.
Uses Windows 'netsh wlan show networks' command for reliable scanning.
"""

import subprocess
import re
import time
import platform
import statistics
from typing import Optional


def scan_wifi() -> list[dict]:
    """
    Scan for nearby WiFi networks and return their details.
    
    Returns:
        List of dicts with keys: bssid, ssid, rssi, channel, auth, signal_percent
    """
    system = platform.system()
    
    if system == "Windows":
        return _scan_windows()
    elif system == "Linux":
        return _scan_linux()
    elif system == "Darwin":
        return _scan_macos()
    else:
        raise RuntimeError(f"Unsupported OS: {system}")


def _scan_windows() -> list[dict]:
    """Scan WiFi networks on Windows using netsh."""
    try:
        # Run netsh command to list all visible networks with BSSID info
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        
        if result.returncode != 0:
            print(f"[WiFi Scanner] netsh error: {result.stderr}")
            return []
        
        return _parse_netsh_output(result.stdout)
    
    except subprocess.TimeoutExpired:
        print("[WiFi Scanner] Scan timed out")
        return []
    except FileNotFoundError:
        print("[WiFi Scanner] netsh command not found")
        return []
    except Exception as e:
        print(f"[WiFi Scanner] Error: {e}")
        return []


def _parse_netsh_output(output: str) -> list[dict]:
    """Parse the output of 'netsh wlan show networks mode=bssid'."""
    networks = []
    current_network = {}
    
    for line in output.split("\n"):
        line = line.strip()
        
        # SSID (not BSSID)
        if line.startswith("SSID") and "BSSID" not in line:
            match = re.match(r"SSID\s+\d+\s*:\s*(.*)", line)
            if match:
                current_network["ssid"] = match.group(1).strip()
        
        # Network type
        elif "Network type" in line or "network type" in line.lower():
            match = re.match(r".*:\s*(.*)", line)
            if match:
                current_network["network_type"] = match.group(1).strip()
        
        # Authentication
        elif "Authentication" in line or "authentication" in line.lower():
            match = re.match(r".*:\s*(.*)", line)
            if match:
                current_network["auth"] = match.group(1).strip()
        
        # BSSID
        elif line.startswith("BSSID"):
            match = re.match(r"BSSID\s+\d+\s*:\s*(.*)", line)
            if match:
                # If we already have a BSSID, save the previous network
                if "bssid" in current_network:
                    networks.append(current_network.copy())
                current_network["bssid"] = match.group(1).strip().lower()
        
        # Signal strength (percentage)
        elif "Signal" in line or "signal" in line.lower():
            match = re.match(r".*:\s*(\d+)%", line)
            if match:
                signal_percent = int(match.group(1))
                current_network["signal_percent"] = signal_percent
                # Convert percentage to approximate dBm
                # Formula: dBm ≈ (signal% / 2) - 100
                current_network["rssi"] = int((signal_percent / 2) - 100)
        
        # Channel
        elif "Channel" in line or "channel" in line.lower():
            match = re.match(r".*:\s*(\d+)", line)
            if match:
                current_network["channel"] = int(match.group(1))
        
        # Radio type (band)
        elif "Radio type" in line or "radio type" in line.lower():
            match = re.match(r".*:\s*(.*)", line)
            if match:
                current_network["radio_type"] = match.group(1).strip()
    
    # Don't forget the last network
    if "bssid" in current_network:
        networks.append(current_network)
    
    return networks


def _scan_linux() -> list[dict]:
    """Scan WiFi networks on Linux using iwlist or nmcli."""
    try:
        # Try nmcli first
        result = subprocess.run(
            ["nmcli", "-t", "-f", "BSSID,SSID,SIGNAL,CHAN,SECURITY", "dev", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        
        if result.returncode == 0:
            networks = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 5:
                    bssid = ":".join(parts[:6]).strip().lower()
                    ssid = parts[6] if len(parts) > 6 else ""
                    signal_percent = int(parts[-3]) if parts[-3].isdigit() else 0
                    channel = int(parts[-2]) if parts[-2].isdigit() else 0
                    auth = parts[-1]
                    
                    networks.append({
                        "bssid": bssid,
                        "ssid": ssid,
                        "signal_percent": signal_percent,
                        "rssi": int((signal_percent / 2) - 100),
                        "channel": channel,
                        "auth": auth,
                    })
            return networks
    except Exception:
        pass
    
    return []


def _scan_macos() -> list[dict]:
    """Scan WiFi networks on macOS using airport utility."""
    try:
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-s"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        
        if result.returncode == 0:
            networks = []
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 7:
                    networks.append({
                        "ssid": parts[0],
                        "bssid": parts[1].lower(),
                        "rssi": int(parts[2]),
                        "signal_percent": max(0, min(100, (int(parts[2]) + 100) * 2)),
                        "channel": int(parts[3].split(",")[0]),
                        "auth": " ".join(parts[6:]),
                    })
            return networks
    except Exception:
        pass
    
    return []


def scan_wifi_averaged(num_scans: int = 3, interval: float = 0.5) -> list[dict]:
    """
    Perform multiple WiFi scans and average the RSSI values for stability.
    
    Args:
        num_scans: Number of scans to average
        interval: Seconds between scans
    
    Returns:
        List of networks with averaged RSSI values
    """
    all_scans = []
    
    for i in range(num_scans):
        scan = scan_wifi()
        all_scans.append(scan)
        if i < num_scans - 1:
            time.sleep(interval)
    
    # Group by BSSID and average RSSI
    bssid_data: dict[str, list[dict]] = {}
    for scan in all_scans:
        for network in scan:
            bssid = network.get("bssid", "")
            if bssid:
                if bssid not in bssid_data:
                    bssid_data[bssid] = []
                bssid_data[bssid].append(network)
    
    # Create averaged results
    averaged = []
    for bssid, entries in bssid_data.items():
        rssi_values = [e["rssi"] for e in entries if "rssi" in e]
        signal_values = [e["signal_percent"] for e in entries if "signal_percent" in e]
        
        avg_network = entries[0].copy()
        if rssi_values:
            avg_network["rssi"] = int(statistics.mean(rssi_values))
        if signal_values:
            avg_network["signal_percent"] = int(statistics.mean(signal_values))
        avg_network["scan_count"] = len(entries)
        
        averaged.append(avg_network)
    
    # Sort by signal strength (strongest first)
    averaged.sort(key=lambda x: x.get("rssi", -100), reverse=True)
    
    return averaged


def get_rssi_vector(networks: list[dict], ap_list: Optional[list[str]] = None) -> dict[str, int]:
    """
    Convert scan results into an RSSI vector keyed by BSSID.
    
    Args:
        networks: List of network dicts from scan_wifi()
        ap_list: Optional list of BSSIDs to include (fills missing with -100)
    
    Returns:
        Dict mapping BSSID → RSSI value
    """
    rssi_map = {}
    for network in networks:
        bssid = network.get("bssid", "")
        rssi = network.get("rssi", -100)
        if bssid:
            rssi_map[bssid] = rssi
    
    # If ap_list provided, ensure all APs are present
    if ap_list:
        result = {}
        for ap in ap_list:
            result[ap] = rssi_map.get(ap, -100)
        return result
    
    return rssi_map


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  WiFi Scanner — Scanning nearby networks...")
    print("=" * 60)
    
    networks = scan_wifi()
    
    if not networks:
        print("\n  ❌ No networks found. Make sure WiFi is enabled.")
    else:
        print(f"\n  ✅ Found {len(networks)} network(s):\n")
        for i, net in enumerate(networks, 1):
            ssid = net.get("ssid", "Hidden")
            rssi = net.get("rssi", "?")
            signal = net.get("signal_percent", "?")
            bssid = net.get("bssid", "?")
            channel = net.get("channel", "?")
            
            # Signal strength bar
            bar_len = max(0, (net.get("signal_percent", 0) // 5))
            bar = "█" * bar_len + "░" * (20 - bar_len)
            
            print(f"  {i}. {ssid}")
            print(f"     BSSID: {bssid}")
            print(f"     Signal: {signal}% ({rssi} dBm) [{bar}]")
            print(f"     Channel: {channel}")
            print()
