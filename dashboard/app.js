/**
 * WiFi Sense Dashboard — Real-time Application Logic
 * ====================================================
 * Handles: API polling, room status, signal display, device list,
 * movement history, calibration modal, and toast notifications.
 */

// ─── Configuration ──────────────────────────────────────────────
const API_BASE = window.location.origin;
const POLL_INTERVAL = 2000;       // 2 seconds
const DEVICE_POLL_INTERVAL = 10000; // 10 seconds

// ─── State ──────────────────────────────────────────────────────
let state = {
    connected: false,
    rooms: [],
    currentRoom: null,
    confidence: 0,
    probabilities: {},
    signals: [],
    devices: [],
    history: [],
    calibrating: false,
    calibrationRoom: null,
};

let pollTimer = null;
let devicePollTimer = null;

// ─── Initialize ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    fetchRooms();
    startPolling();
    setupEventListeners();
});

// ─── Event Listeners ────────────────────────────────────────────
function setupEventListeners() {
    // Calibrate button
    document.getElementById('btn-calibrate').addEventListener('click', openCalibrationModal);
    
    // Modal close
    document.getElementById('modal-close').addEventListener('click', closeCalibrationModal);
    document.getElementById('calibrate-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeCalibrationModal();
    });
    
    // Train model button
    document.getElementById('btn-train-model').addEventListener('click', trainModel);
    
    // Refresh devices
    document.getElementById('btn-refresh-devices').addEventListener('click', fetchDevices);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeCalibrationModal();
    });
}

// ─── API Calls ──────────────────────────────────────────────────
async function apiFetch(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        setConnected(true);
        return data;
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        setConnected(false);
        return null;
    }
}

// ─── Polling ────────────────────────────────────────────────────
function startPolling() {
    fetchStatus();
    fetchSignals();
    fetchDevices();
    fetchHistory();
    
    pollTimer = setInterval(() => {
        fetchStatus();
        fetchSignals();
    }, POLL_INTERVAL);
    
    devicePollTimer = setInterval(() => {
        fetchDevices();
        fetchHistory();
    }, DEVICE_POLL_INTERVAL);
}

function stopPolling() {
    clearInterval(pollTimer);
    clearInterval(devicePollTimer);
}

// ─── Fetch Functions ────────────────────────────────────────────
async function fetchRooms() {
    const data = await apiFetch('/api/rooms');
    if (data) {
        state.rooms = data.rooms || [];
        renderFloorPlan();
        renderCalibrationRooms();
    }
}

async function fetchStatus() {
    const data = await apiFetch('/api/status');
    if (data) {
        state.currentRoom = data.current_room;
        state.confidence = data.confidence || 0;
        state.probabilities = data.probabilities || {};
        
        updateCurrentRoomDisplay(data);
        updateFloorPlanActive(data.current_room, data.probabilities);
        renderProbabilities();
    }
}

async function fetchSignals() {
    const data = await apiFetch('/api/signals');
    if (data) {
        state.signals = data.networks || [];
        renderSignals();
        updateNetworksCount(state.signals.length);
    }
}

async function fetchDevices() {
    const data = await apiFetch('/api/devices');
    if (data) {
        state.devices = data.devices || [];
        renderDevices();
        updateDevicesCount(state.devices.filter(d => d.online).length);
    }
}

async function fetchHistory() {
    const data = await apiFetch('/api/history');
    if (data) {
        state.history = data.history || [];
        renderHistory();
    }
}

// ─── Connection Status ─────────────────────────────────────────
function setConnected(connected) {
    state.connected = connected;
    const el = document.getElementById('connection-status');
    
    if (connected) {
        el.className = 'status-indicator connected';
        el.querySelector('span').textContent = 'Connected';
    } else {
        el.className = 'status-indicator disconnected';
        el.querySelector('span').textContent = 'Disconnected';
    }
}

// ─── Update Display Functions ───────────────────────────────────
function updateCurrentRoomDisplay(data) {
    const nameEl = document.getElementById('current-room-name');
    const confEl = document.getElementById('confidence-value');
    const iconEl = document.getElementById('stat-current-room').querySelector('.stat-icon');
    
    if (data.current_room) {
        const room = findRoom(data.current_room);
        nameEl.textContent = room ? room.name : data.current_room;
        iconEl.textContent = room ? room.icon : '📍';
        confEl.textContent = `${Math.round(data.confidence * 100)}%`;
        
        // Color the confidence based on value
        if (data.confidence >= 0.7) {
            confEl.style.color = 'var(--accent-green)';
        } else if (data.confidence >= 0.4) {
            confEl.style.color = 'var(--accent-orange)';
        } else {
            confEl.style.color = 'var(--accent-red)';
        }
    } else {
        nameEl.textContent = data.error || 'Scanning...';
        iconEl.textContent = '📍';
        confEl.textContent = '—';
        confEl.style.color = '';
    }
}

function updateNetworksCount(count) {
    document.getElementById('networks-count').textContent = count;
}

function updateDevicesCount(count) {
    document.getElementById('devices-count').textContent = count;
}

// ─── Floor Plan Rendering ───────────────────────────────────────
function renderFloorPlan() {
    const container = document.getElementById('floor-plan');
    container.innerHTML = '';
    
    state.rooms.forEach(room => {
        const cell = document.createElement('div');
        cell.className = 'room-cell';
        cell.id = `room-${room.id}`;
        cell.style.setProperty('--room-color', room.color);
        cell.style.setProperty('--room-color-glow', room.color + '30');
        
        cell.innerHTML = `
            <div class="room-confidence" id="confidence-${room.id}">0%</div>
            <div class="room-icon">${room.icon}</div>
            <div class="room-name">${room.name}</div>
            <div class="room-status">
                <div class="room-status-dot"></div>
                <span>Empty</span>
            </div>
            <div class="person-indicator">
                👤 Person Detected
            </div>
        `;
        
        container.appendChild(cell);
    });
}

function updateFloorPlanActive(activeRoomId, probabilities) {
    state.rooms.forEach(room => {
        const cell = document.getElementById(`room-${room.id}`);
        if (!cell) return;
        
        const isActive = room.id === activeRoomId;
        cell.classList.toggle('active', isActive);
        
        // Update status text
        const statusText = cell.querySelector('.room-status span');
        statusText.textContent = isActive ? 'Occupied' : 'Empty';
        
        // Update confidence badge
        const confBadge = document.getElementById(`confidence-${room.id}`);
        const prob = probabilities[room.id];
        if (prob !== undefined) {
            confBadge.textContent = `${Math.round(prob * 100)}%`;
        }
    });
}

// ─── Signal Strength Rendering ──────────────────────────────────
function renderSignals() {
    const container = document.getElementById('signals-list');
    
    if (!state.signals.length) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📡</span>
                <p>No networks found</p>
            </div>
        `;
        return;
    }
    
    // Sort by signal strength
    const sorted = [...state.signals].sort((a, b) => (b.signal_percent || 0) - (a.signal_percent || 0));
    
    container.innerHTML = sorted.slice(0, 10).map(net => {
        const ssid = net.ssid || 'Hidden Network';
        const signal = net.signal_percent || 0;
        const rssi = net.rssi || -100;
        
        return `
            <div class="signal-item">
                <div class="signal-ssid" title="${ssid}">${ssid}</div>
                <div class="signal-bar-container">
                    <div class="signal-bar-fill" style="width: ${signal}%"></div>
                </div>
                <div class="signal-dbm">${rssi} dBm</div>
            </div>
        `;
    }).join('');
}

// ─── Devices Rendering ──────────────────────────────────────────
function renderDevices() {
    const container = document.getElementById('devices-list');
    
    if (!state.devices.length) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📱</span>
                <p>No devices found</p>
            </div>
        `;
        return;
    }
    
    const deviceIcons = {
        phone: '📱',
        computer: '💻',
        tv: '📺',
        printer: '🖨️',
        router: '🌐',
        smart_device: '🏠',
        unknown: '❓',
    };
    
    container.innerHTML = state.devices.map(dev => {
        const icon = deviceIcons[dev.type] || '❓';
        const statusClass = dev.online ? 'online' : 'offline';
        
        return `
            <div class="device-item">
                <div class="device-icon">${icon}</div>
                <div class="device-info">
                    <div class="device-name">${dev.hostname || dev.mac}</div>
                    <div class="device-ip">${dev.ip} · ${dev.vendor || 'Unknown'}</div>
                </div>
                <div class="device-status ${statusClass}"></div>
            </div>
        `;
    }).join('');
}

// ─── Probabilities Rendering ────────────────────────────────────
function renderProbabilities() {
    const container = document.getElementById('probabilities-chart');
    
    if (!Object.keys(state.probabilities).length) {
        container.innerHTML = state.rooms.map(room => {
            return `
                <div class="prob-item">
                    <div class="prob-label">
                        <span class="prob-label-icon">${room.icon}</span>
                        ${room.name}
                    </div>
                    <div class="prob-bar-container">
                        <div class="prob-bar-fill" style="width: 0%; background: ${room.color}"></div>
                    </div>
                    <div class="prob-value">—</div>
                </div>
            `;
        }).join('');
        return;
    }
    
    container.innerHTML = state.rooms.map(room => {
        const prob = state.probabilities[room.id] || 0;
        const percent = Math.round(prob * 100);
        const isActive = room.id === state.currentRoom;
        
        return `
            <div class="prob-item ${isActive ? 'active' : ''}">
                <div class="prob-label">
                    <span class="prob-label-icon">${room.icon}</span>
                    ${room.name}
                </div>
                <div class="prob-bar-container">
                    <div class="prob-bar-fill" style="width: ${percent}%; background: ${room.color}"></div>
                </div>
                <div class="prob-value">${percent}%</div>
            </div>
        `;
    }).join('');
}

// ─── Movement History Rendering ─────────────────────────────────
function renderHistory() {
    const container = document.getElementById('history-timeline');
    const countBadge = document.getElementById('history-count');
    
    countBadge.textContent = `${state.history.length} events`;
    
    if (!state.history.length) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">🕐</span>
                <p>No movement detected yet</p>
            </div>
        `;
        return;
    }
    
    // Show most recent first
    const reversed = [...state.history].reverse();
    
    container.innerHTML = reversed.slice(0, 15).map((entry, index) => {
        const time = formatTime(entry.timestamp);
        const fromIcon = getRoomIcon(entry.from_room);
        const toIcon = getRoomIcon(entry.to_room);
        
        return `
            <div class="history-item">
                <div class="history-dot-line">
                    <div class="history-dot"></div>
                    ${index < reversed.length - 1 ? '<div class="history-line"></div>' : ''}
                </div>
                <div class="history-content">
                    <div class="history-movement">
                        ${fromIcon} ${entry.from_name}
                        <span class="arrow">→</span>
                        ${toIcon} ${entry.to_name}
                    </div>
                    <div class="history-time">${time}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ─── Calibration Modal ──────────────────────────────────────────
function openCalibrationModal() {
    document.getElementById('calibrate-modal').classList.add('active');
    fetchCalibrationStatus();
}

function closeCalibrationModal() {
    document.getElementById('calibrate-modal').classList.remove('active');
    document.getElementById('calibration-progress').style.display = 'none';
}

async function fetchCalibrationStatus() {
    const data = await apiFetch('/api/calibrate/status');
    if (data) {
        renderCalibrationRooms(data.status);
        
        // Show train button if at least 2 rooms are calibrated
        const calibratedCount = Object.values(data.status || {}).filter(s => s.calibrated).length;
        document.getElementById('btn-train-model').style.display = calibratedCount >= 2 ? 'block' : 'none';
    }
}

function renderCalibrationRooms(status = {}) {
    const container = document.getElementById('calibration-rooms');
    
    container.innerHTML = state.rooms.map(room => {
        const roomStatus = status[room.id] || {};
        const isCalibrated = roomStatus.calibrated || false;
        const scans = roomStatus.total_scans || 0;
        
        return `
            <div class="calibration-room" id="cal-room-${room.id}">
                <div class="calibration-room-icon">${room.icon}</div>
                <div class="calibration-room-info">
                    <div class="calibration-room-name">${room.name}</div>
                    <div class="calibration-room-status ${isCalibrated ? 'done' : ''}">
                        ${isCalibrated ? `✅ Calibrated (${scans} scans)` : '❌ Not calibrated'}
                    </div>
                </div>
                <button class="btn btn-sm ${isCalibrated ? 'btn-ghost' : 'btn-primary'}"
                        onclick="startCalibration('${room.id}', '${room.name}')">
                    ${isCalibrated ? '🔄 Redo' : '▶️ Start'}
                </button>
            </div>
        `;
    }).join('');
}

async function startCalibration(roomId, roomName) {
    if (state.calibrating) return;
    
    state.calibrating = true;
    state.calibrationRoom = roomId;
    
    const progressEl = document.getElementById('calibration-progress');
    const fillEl = document.getElementById('calibration-fill');
    const roomNameEl = document.getElementById('calibration-room-name');
    const percentEl = document.getElementById('calibration-percent');
    const hintEl = document.getElementById('calibration-hint');
    
    progressEl.style.display = 'block';
    roomNameEl.textContent = `📡 ${roomName}`;
    hintEl.textContent = `${roomName} mein raho — WiFi signals record ho rahe hain...`;
    fillEl.style.width = '0%';
    percentEl.textContent = '0%';
    
    showToast('info', `${roomName} ki calibration shuru ho gayi. Apni jagah par raho!`);
    
    try {
        const data = await apiFetch('/api/calibrate/start', {
            method: 'POST',
            body: JSON.stringify({ room_id: roomId }),
        });
        
        if (data && data.success) {
            // Poll for calibration progress
            const progressInterval = setInterval(async () => {
                const status = await apiFetch('/api/calibrate/progress');
                if (status) {
                    const pct = status.progress || 0;
                    fillEl.style.width = `${pct}%`;
                    percentEl.textContent = `${pct}%`;
                    
                    if (pct >= 100 || status.done) {
                        clearInterval(progressInterval);
                        state.calibrating = false;
                        showToast('success', `${roomName} calibrate ho gaya! ✅`);
                        fetchCalibrationStatus();
                        
                        setTimeout(() => {
                            progressEl.style.display = 'none';
                        }, 1500);
                    }
                }
            }, 1000);
        } else {
            state.calibrating = false;
            showToast('error', 'Calibration start nahi ho saki. Dobara try karo.');
            progressEl.style.display = 'none';
        }
    } catch (error) {
        state.calibrating = false;
        showToast('error', 'Calibration mein error. Dobara try karo.');
        progressEl.style.display = 'none';
    }
}

async function trainModel() {
    showToast('info', '🧠 Model training shuru... Thoda wait karo.');
    
    const data = await apiFetch('/api/train', { method: 'POST' });
    
    if (data && data.success) {
        showToast('success', `Model train ho gaya! Accuracy: ${Math.round(data.accuracy * 100)}%`);
        closeCalibrationModal();
    } else {
        showToast('error', data?.error || 'Model training fail. Pehle rooms calibrate karo.');
    }
}

// ─── Utility Functions ──────────────────────────────────────────
function findRoom(roomId) {
    return state.rooms.find(r => r.id === roomId);
}

function getRoomIcon(roomId) {
    const room = findRoom(roomId);
    return room ? room.icon : '📍';
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = (now - date) / 1000;
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    
    return date.toLocaleString('en-PK', {
        hour: '2-digit',
        minute: '2-digit',
        day: 'numeric',
        month: 'short',
    });
}

// ─── Toast Notifications ────────────────────────────────────────
function showToast(type, message, duration = 4000) {
    const container = document.getElementById('toast-container');
    
    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️',
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ─── Expose to global for onclick handlers ──────────────────────
window.startCalibration = startCalibration;
