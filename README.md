# 📡 WiFi Sense — Room Detection System

> **WiFi signals ki madad se pata lagao ke kaun kis room mein hai!**

A real-time human presence detection and room-level localization system that uses WiFi signal fingerprinting (RSSI) and machine learning to determine which room a person is in.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-green?style=flat-square&logo=flask)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-orange?style=flat-square&logo=scikit-learn)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)

---

## 🌟 Features

- **📍 Room-Level Detection** — Pata lagao ke koi shakhs kis room mein hai
- **📡 WiFi Signal Monitoring** — Real-time RSSI (signal strength) tracking
- **🧠 ML-Powered** — Random Forest classifier for accurate room prediction
- **🖥️ Beautiful Dashboard** — Dark glassmorphism UI with live updates
- **📱 Device Tracking** — Network pe connected devices ki monitoring
- **🕐 Movement History** — Track karo ke log kab kahan gaye
- **⚙️ Easy Calibration** — Simple room-by-room setup process
- **🪟 Windows Compatible** — Works with standard WiFi adapters (no special hardware)

---

## 🏗️ How It Works

```
WiFi Router  →  Signal Scanning  →  ML Model  →  Room Prediction  →  Dashboard
   📡             📊                  🧠              📍                🖥️
```

### Kaise Kaam Karta Hai?

1. **Calibration Phase**: Har room mein jaake WiFi signals record karo (fingerprint)
2. **Training Phase**: ML model train hota hai fingerprints se
3. **Detection Phase**: Real-time mein current signals se room predict hota hai

WiFi signals har room mein differently behave karti hain — walls, furniture, aur objects ki wajah se signal strength change hoti hai. System ye patterns seekh ke batata hai ke aap kis room mein ho.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Calibrate Rooms

```bash
python calibrate.py
```

Ye interactive tool hai — har room mein jaake WiFi signals record karo:
- Room mein jao
- Enter dabo
- 30 seconds wait karo
- Agla room

### 3. Start Detection

```bash
python detect.py
```

Browser automatically open hoga `http://localhost:5000` pe — beautiful dashboard dikhega!

---

## 📁 Project Structure

```
wifi/
├── 📄 config.py              # Configuration (rooms, intervals, model settings)
├── 📄 server.py               # Flask API server
├── 📄 calibrate.py            # Room calibration CLI tool
├── 📄 detect.py               # Main entry point
├── 📁 scanner/
│   ├── wifi_scanner.py        # WiFi RSSI scanning (Windows/Linux/Mac)
│   └── device_tracker.py      # Network device detection
├── 📁 ml/
│   ├── fingerprint.py         # Room fingerprint collection
│   ├── model.py               # Random Forest ML model
│   └── predictor.py           # Real-time room prediction
├── 📁 dashboard/
│   ├── index.html             # Web dashboard UI
│   ├── style.css              # Premium dark-mode styles
│   └── app.js                 # Dashboard logic
├── 📁 data/
│   ├── fingerprints/          # Saved room fingerprints
│   └── models/                # Trained ML models
└── 📄 requirements.txt        # Python dependencies
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Room definitions — apne rooms ke naam dalo
ROOMS = [
    {"id": "room_1", "name": "Bedroom",    "color": "#6366f1", "icon": "🛏️"},
    {"id": "room_2", "name": "Living Room", "color": "#8b5cf6", "icon": "🛋️"},
    {"id": "room_3", "name": "Kitchen",     "color": "#ec4899", "icon": "🍳"},
    {"id": "room_4", "name": "Bathroom",    "color": "#14b8a6", "icon": "🚿"},
]

# Scanner settings
SCAN_INTERVAL = 2        # seconds between scans
CALIBRATION_DURATION = 30 # seconds per room calibration
```

---

## 🖥️ CLI Commands

```bash
# Interactive calibration
python calibrate.py

# Calibrate specific room
python calibrate.py --room 1

# Check calibration status
python calibrate.py --status

# Train model only
python calibrate.py --train

# Reset all calibration data
python calibrate.py --reset

# Start detection with dashboard
python detect.py

# CLI-only detection (no browser)
python detect.py --cli

# Custom port
python detect.py --port 8080
```

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Current room detection status |
| `/api/rooms` | GET | All room definitions |
| `/api/signals` | GET | Live WiFi signal data |
| `/api/devices` | GET | Connected network devices |
| `/api/history` | GET | Movement history |
| `/api/calibrate/start` | POST | Start room calibration |
| `/api/calibrate/progress` | GET | Calibration progress |
| `/api/train` | POST | Train ML model |

---

## 🛠️ Requirements

- **Python 3.9+**
- **WiFi adapter** (built-in laptop WiFi works fine)
- **Windows 10/11** (primary support), Linux, or macOS
- No special hardware needed!

---

## 📊 Accuracy Tips

- **Zyada scans = Better accuracy**: Calibration duration badha do (`config.py`)
- **Multiple times calibrate karo**: Har room ko 2-3 baar calibrate karo
- **Different positions**: Room ke alag alag corners se calibrate karo
- **Consistent environment**: Calibration ke waqt doors/windows same position mein rakho

---

## 📝 License

MIT License — Free to use, modify, and distribute.

---

## 🤝 Contributing

Pull requests welcome! Issues report karo GitHub pe.

---

**Made with ❤️ using WiFi signals** | [GitHub Repository](https://github.com/Shifrozy/building-a-wifi-sensing-system)
