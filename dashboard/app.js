/**
 * WiFi Sense — 3D Radar Visualization
 * =====================================
 * Three.js powered 3D room with:
 * - Animated WiFi signal waves (expanding rings)
 * - Room walls as transparent barriers
 * - Radar sweep effect on floor
 * - Glowing person silhouette on detection
 * - Real-time API integration
 */

// ═══════════════════════════════════════════════════════════════
//  CONFIGURATION
// ═══════════════════════════════════════════════════════════════
const CONFIG = {
    room: { width: 6, height: 3, depth: 5 },
    router: { x: -2.5, y: 2.5, z: -2 },
    api: window.location.origin,
    pollInterval: 2000,
    waveSpeed: 2.5,
    waveMaxRadius: 8,
    waveCount: 6,
    sweepSpeed: 1.2,
};

// ═══════════════════════════════════════════════════════════════
//  GLOBALS
// ═══════════════════════════════════════════════════════════════
let scene, camera, renderer, controls;
let clock, animationId;
let roomGroup, wavesGroup, sweepMesh;
let routerMesh, routerGlow;
let persons = [];
const MAX_PERSONS = 3;
let floorGrid;
let waves = [];
let showWaves = true;
let showGrid = true;

// Custom Shader Materials
let radarUniforms = {
    time: { value: 0 },
    routerPos: { value: new THREE.Vector3(CONFIG.router.x, CONFIG.router.y, CONFIG.router.z) },
    waveSpeed: { value: CONFIG.waveSpeed },
    waveSpacing: { value: CONFIG.waveMaxRadius / CONFIG.waveCount },
    maxRadius: { value: CONFIG.waveMaxRadius },
};

const radarVertexShader = `
    varying vec3 vWorldPosition;
    varying vec3 vNormal;
    void main() {
        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
        vWorldPosition = worldPosition.xyz;
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * viewMatrix * worldPosition;
    }
`;

const radarFragmentShader = `
    uniform float time;
    uniform vec3 routerPos;
    uniform float waveSpeed;
    uniform float waveSpacing;
    uniform float maxRadius;
    
    uniform vec3 baseColor;
    uniform float opacityMult;
    uniform float isWireframe;
    
    varying vec3 vWorldPosition;
    varying vec3 vNormal;
    
    void main() {
        float dist = distance(vWorldPosition, routerPos);
        if (dist > maxRadius) discard;
        
        // Calculate expanding waves
        float wavePhase = mod(dist - time * waveSpeed, waveSpacing);
        
        // Ring thickness
        float thickness = 0.2;
        float ring = 0.0;
        if (wavePhase > waveSpacing - thickness) {
            ring = smoothstep(waveSpacing - thickness, waveSpacing, wavePhase);
        }
        
        // Edge glow (Fresnel) for solid objects
        float edgeGlow = 1.0;
        if (isWireframe < 0.5) {
            vec3 viewDir = normalize(cameraPosition - vWorldPosition);
            float fresnel = 1.0 - max(dot(viewDir, vNormal), 0.0);
            edgeGlow = pow(fresnel, 2.0) + 0.2;
        }
        
        // Fade out over distance
        float fade = 1.0 - (dist / maxRadius);
        
        // Final alpha
        float alpha = ring * fade * edgeGlow * opacityMult;
        
        if (alpha < 0.02) discard;
        
        // Add core glow
        vec3 finalColor = baseColor + (baseColor * ring * 2.0);
        
        gl_FragColor = vec4(finalColor, min(alpha, 1.0));
    }
`;

// Detection state
let state = {
    connected: false,
    motionDetected: false,
    presenceDetected: false,
    motionIntensity: 0,
    confidence: 0,
    personPos: { x: 0, z: 0 },
    personCount: 0,
    signals: [],
    scanCount: 0,
    baselineReady: false,
    numNetworks: 0,
    personVisible: false,
    targetPersonVisible: false,
    personOpacity: 0,
};

let prevMotionState = false;
let logEntries = [];
let fpsFrames = 0;
let fpsTime = 0;

// ═══════════════════════════════════════════════════════════════
//  INITIALIZATION
// ═══════════════════════════════════════════════════════════════
function init() {
    clock = new THREE.Clock();

    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000008);
    scene.fog = new THREE.FogExp2(0x000008, 0.035);

    // Camera
    camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(6, 7, 8);
    camera.lookAt(0, 0, 0);

    // Renderer
    const canvas = document.getElementById('radar-canvas');
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // Controls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = 4;
    controls.maxDistance = 20;
    controls.target.set(0, 1, 0);

    // Lighting
    setupLighting();

    // Build scene
    createRoom();
    createRouter();
    createWaves();
    createRadarSweep();
    createPerson();
    createFloorGrid();

    // Events
    window.addEventListener('resize', onResize);
    setupUIEvents();

    // Start
    startPolling();
    animate();

    addLogEntry('system', 'System initialized');
    addLogEntry('system', 'Collecting baseline...');
}

// ═══════════════════════════════════════════════════════════════
//  LIGHTING
// ═══════════════════════════════════════════════════════════════
function setupLighting() {
    // Ambient
    const ambient = new THREE.AmbientLight(0x112244, 0.4);
    scene.add(ambient);

    // Main directional
    const dirLight = new THREE.DirectionalLight(0x4488cc, 0.3);
    dirLight.position.set(5, 10, 5);
    scene.add(dirLight);

    // Router point light (cyan glow)
    const routerLight = new THREE.PointLight(0x00c8ff, 1.5, 10);
    routerLight.position.set(CONFIG.router.x, CONFIG.router.y, CONFIG.router.z);
    scene.add(routerLight);

    // Subtle bottom glow
    const bottomLight = new THREE.PointLight(0x0044ff, 0.5, 8);
    bottomLight.position.set(0, -1, 0);
    scene.add(bottomLight);
}

// ═══════════════════════════════════════════════════════════════
//  ROOM
// ═══════════════════════════════════════════════════════════════
function createRoom() {
    roomGroup = new THREE.Group();
    const { width, height, depth } = CONFIG.room;
    const hw = width / 2, hd = depth / 2;

    // Base radar material factory
    const createRadarMaterial = (color, isWireframe = false, opacity = 1.0) => {
        return new THREE.ShaderMaterial({
            uniforms: {
                ...radarUniforms,
                baseColor: { value: new THREE.Color(color) },
                opacityMult: { value: opacity },
                isWireframe: { value: isWireframe ? 1.0 : 0.0 }
            },
            vertexShader: radarVertexShader,
            fragmentShader: radarFragmentShader,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
    };

    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floorMat = createRadarMaterial(0x00c8ff, false, 0.4);
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    roomGroup.add(floor);

    // Wall material
    const wallMat = createRadarMaterial(0x00c8ff, false, 0.6);
    // Wall edge material
    const edgeMat = createRadarMaterial(0x00ffcc, true, 2.0);

    // Create 4 walls
    const walls = [
        { pos: [0, height/2, -hd], rot: [0, 0, 0], size: [width, height] },           // Back
        { pos: [0, height/2, hd], rot: [0, Math.PI, 0], size: [width, height] },       // Front
        { pos: [-hw, height/2, 0], rot: [0, Math.PI/2, 0], size: [depth, height] },    // Left
        { pos: [hw, height/2, 0], rot: [0, -Math.PI/2, 0], size: [depth, height] },    // Right
    ];

    walls.forEach(w => {
        const geo = new THREE.PlaneGeometry(w.size[0], w.size[1]);
        const mesh = new THREE.Mesh(geo, wallMat);
        mesh.position.set(...w.pos);
        mesh.rotation.set(...w.rot);
        roomGroup.add(mesh);

        // Edge wireframe
        const edgeGeo = new THREE.EdgesGeometry(geo);
        const edgeLine = new THREE.LineSegments(edgeGeo, edgeMat);
        edgeLine.position.copy(mesh.position);
        edgeLine.rotation.copy(mesh.rotation);
        roomGroup.add(edgeLine);
    });

    scene.add(roomGroup);
}

// ═══════════════════════════════════════════════════════════════
//  FLOOR GRID
// ═══════════════════════════════════════════════════════════════
function createFloorGrid() {
    const gridHelper = new THREE.GridHelper(
        Math.max(CONFIG.room.width, CONFIG.room.depth),
        Math.max(CONFIG.room.width, CONFIG.room.depth) * 2,
        0x003355,
        0x001122
    );
    gridHelper.position.y = 0.01;
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = 0.4;
    floorGrid = gridHelper;
    scene.add(floorGrid);
}

// ═══════════════════════════════════════════════════════════════
//  ROUTER
// ═══════════════════════════════════════════════════════════════
function createRouter() {
    // Router body
    const routerGeo = new THREE.BoxGeometry(0.3, 0.08, 0.2);
    const routerMat = new THREE.MeshStandardMaterial({
        color: 0x222233,
        emissive: 0x00c8ff,
        emissiveIntensity: 0.3,
        metalness: 0.8,
        roughness: 0.2,
    });
    routerMesh = new THREE.Mesh(routerGeo, routerMat);
    routerMesh.position.set(CONFIG.router.x, CONFIG.router.y, CONFIG.router.z);
    scene.add(routerMesh);

    // Antennas
    const antGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.3, 8);
    const antMat = new THREE.MeshStandardMaterial({ color: 0x333344, metalness: 0.9 });

    [-0.08, 0.08].forEach(offset => {
        const ant = new THREE.Mesh(antGeo, antMat);
        ant.position.set(
            CONFIG.router.x + offset,
            CONFIG.router.y + 0.19,
            CONFIG.router.z
        );
        scene.add(ant);
    });

    // Router glow sphere
    const glowGeo = new THREE.SphereGeometry(0.15, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
        color: 0x00c8ff,
        transparent: true,
        opacity: 0.15,
    });
    routerGlow = new THREE.Mesh(glowGeo, glowMat);
    routerGlow.position.copy(routerMesh.position);
    scene.add(routerGlow);
}

// ═══════════════════════════════════════════════════════════════
//  SIGNAL WAVES
// ═══════════════════════════════════════════════════════════════
function createWaves() {
    wavesGroup = new THREE.Group();
    scene.add(wavesGroup);

    for (let i = 0; i < CONFIG.waveCount; i++) {
        const wave = createSingleWave(i);
        waves.push(wave);
        wavesGroup.add(wave.mesh);
    }
}

function createSingleWave(index) {
    const geo = new THREE.RingGeometry(0.1, 0.15, 64);
    const mat = new THREE.MeshBasicMaterial({
        color: 0x00c8ff,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(CONFIG.router.x, CONFIG.router.y, CONFIG.router.z);
    mesh.rotation.x = -Math.PI / 2;

    return {
        mesh,
        radius: (index / CONFIG.waveCount) * CONFIG.waveMaxRadius,
        speed: CONFIG.waveSpeed,
        maxRadius: CONFIG.waveMaxRadius,
    };
}

function updateWaves(delta) {
    if (!showWaves) {
        wavesGroup.visible = false;
        return;
    }
    wavesGroup.visible = true;

    waves.forEach(wave => {
        wave.radius += wave.speed * delta;

        if (wave.radius > wave.maxRadius) {
            wave.radius = 0;
        }

        // Update ring geometry
        const innerR = Math.max(0.01, wave.radius);
        const outerR = innerR + 0.08 + wave.radius * 0.02;

        wave.mesh.geometry.dispose();
        wave.mesh.geometry = new THREE.RingGeometry(innerR, outerR, 64);

        // Fade out as it expands
        const t = wave.radius / wave.maxRadius;
        wave.mesh.material.opacity = Math.max(0, 0.4 * (1 - t * t));

        // Color shifts when motion detected
        if (state.motionDetected && t > 0.3 && t < 0.7) {
            wave.mesh.material.color.setHex(0xff3366);
        } else {
            wave.mesh.material.color.setHex(0x00c8ff);
        }

        // Scale from router position
        wave.mesh.position.set(CONFIG.router.x, CONFIG.router.y, CONFIG.router.z);
        wave.mesh.scale.set(1, 1, 1);
    });
}

// ═══════════════════════════════════════════════════════════════
//  RADAR SWEEP
// ═══════════════════════════════════════════════════════════════
function createRadarSweep() {
    // Sweep cone on the floor
    const sweepGeo = new THREE.CircleGeometry(
        Math.max(CONFIG.room.width, CONFIG.room.depth) * 0.6,
        64, 0, Math.PI / 6
    );
    const sweepMat = new THREE.MeshBasicMaterial({
        color: 0x00c8ff,
        transparent: true,
        opacity: 0.06,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    sweepMesh = new THREE.Mesh(sweepGeo, sweepMat);
    sweepMesh.rotation.x = -Math.PI / 2;
    sweepMesh.position.set(CONFIG.router.x, 0.02, CONFIG.router.z);
    scene.add(sweepMesh);
}

function updateSweep(elapsed) {
    const angle = elapsed * CONFIG.sweepSpeed;
    sweepMesh.rotation.z = angle;

    // Pulse opacity
    const pulse = 0.04 + Math.sin(elapsed * 3) * 0.02;
    sweepMesh.material.opacity = pulse;
}

// ═══════════════════════════════════════════════════════════════
//  PERSON
// ═══════════════════════════════════════════════════════════════
function createPerson() {
    const bodyColor = 0xff1144;

    const createPersonRadarMaterial = (opacity = 1.5) => {
        return new THREE.ShaderMaterial({
            uniforms: {
                ...radarUniforms,
                baseColor: { value: new THREE.Color(bodyColor) },
                opacityMult: { value: opacity },
                isWireframe: { value: 0.0 }
            },
            vertexShader: radarVertexShader,
            fragmentShader: radarFragmentShader,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
    };

    for (let i = 0; i < MAX_PERSONS; i++) {
        const group = new THREE.Group();
        group.visible = false;
        scene.add(group);

        const torsoMat = createPersonRadarMaterial(2.0);

        // Torso
        const torsoGeo = new THREE.CylinderGeometry(0.2, 0.18, 0.7, 16);
        const torso = new THREE.Mesh(torsoGeo, torsoMat);
        torso.position.y = 1.1;
        group.add(torso);

        // Head
        const headGeo = new THREE.SphereGeometry(0.15, 16, 16);
        const head = new THREE.Mesh(headGeo, torsoMat);
        head.position.y = 1.6;
        group.add(head);

        // Legs
        const legGeo = new THREE.CylinderGeometry(0.08, 0.06, 0.7, 8);
        [-0.1, 0.1].forEach(offset => {
            const leg = new THREE.Mesh(legGeo, torsoMat);
            leg.position.set(offset, 0.35, 0);
            group.add(leg);
        });

        // Arms
        const armGeo = new THREE.CylinderGeometry(0.05, 0.04, 0.55, 8);
        [-0.28, 0.28].forEach(offset => {
            const arm = new THREE.Mesh(armGeo, torsoMat);
            arm.position.set(offset, 1.05, 0);
            arm.rotation.z = offset > 0 ? -0.15 : 0.15;
            group.add(arm);
        });

        // Ground ring indicator
        const ringGeo = new THREE.RingGeometry(0.3, 0.35, 32);
        const ringMat = new THREE.MeshBasicMaterial({
            color: 0xff3366,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.02;
        group.add(ring);

        persons.push({
            group: group,
            glowMesh: ring,
            opacity: 0,
            offset: { x: (i - 1) * 0.4, z: (i % 2) * 0.4 - 0.2 } // Spread them out slightly
        });
    }
}

function updatePerson(elapsed) {
    const hw = CONFIG.room.width / 2;
    const hd = CONFIG.room.depth / 2;
    
    // Base position
    const targetX = state.personPos.x * hw * 0.8;
    const targetZ = state.personPos.z * hd * 0.8;

    for (let i = 0; i < MAX_PERSONS; i++) {
        const p = persons[i];
        const isTargetVisible = (state.motionDetected || state.presenceDetected) && (i < state.personCount);

        // Smooth opacity transition
        if (isTargetVisible) {
            p.opacity = Math.min(1, p.opacity + 0.03);
        } else {
            p.opacity = Math.max(0, p.opacity - 0.01);
        }

        p.group.visible = p.opacity > 0.01;

        if (!p.group.visible) continue;

        // Only manipulate the ground ring's opacity
        if (p.glowMesh && p.glowMesh.material) {
            p.glowMesh.material.opacity = 0.3 * p.opacity;
        }

        // Apply spread offset to positions
        const px = targetX + p.offset.x;
        const pz = targetZ + p.offset.z;

        // Smooth movement
        p.group.position.x += (px - p.group.position.x) * 0.05;
        p.group.position.z += (pz - p.group.position.z) * 0.05;

        // Subtle breathing animation
        const breathe = Math.sin(elapsed * 2 + i) * 0.02;
        p.group.position.y = breathe;
    }
}

// ═══════════════════════════════════════════════════════════════
//  ANIMATION LOOP
// ═══════════════════════════════════════════════════════════════
function animate() {
    animationId = requestAnimationFrame(animate);

    const delta = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    // Update global shader time for the radar pulse
    radarUniforms.time.value = elapsed;

    // Update controls
    controls.update();

    // Animate elements
    updateSweep(elapsed);
    updatePerson(elapsed);
    updateRouter(elapsed);

    // Render
    renderer.render(scene, camera);

    // FPS counter
    fpsFrames++;
    if (elapsed - fpsTime >= 1) {
        document.getElementById('fps-counter').textContent = `${fpsFrames} FPS`;
        fpsFrames = 0;
        fpsTime = elapsed;
    }
}

function updateRouter(elapsed) {
    if (routerGlow) {
        const pulse = 0.12 + Math.sin(elapsed * 3) * 0.05;
        routerGlow.material.opacity = pulse;
        routerGlow.scale.setScalar(1 + Math.sin(elapsed * 2) * 0.1);
    }
}

// ═══════════════════════════════════════════════════════════════
//  API POLLING
// ═══════════════════════════════════════════════════════════════
function startPolling() {
    fetchRadar();
    setInterval(fetchRadar, CONFIG.pollInterval);
}

async function fetchRadar() {
    try {
        const res = await fetch(`${CONFIG.api}/api/radar`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        setConnected(true);

        // Update state
        const prevMotion = state.motionDetected;

        state.motionDetected = data.motion_detected || false;
        state.presenceDetected = data.presence_detected || false;
        state.motionIntensity = data.motion_intensity || 0;
        state.confidence = data.detection_confidence || 0;
        state.personPos = data.person_position || { x: 0, z: 0 };
        state.personCount = data.person_count || 0;
        state.signals = data.signal_data || [];
        state.scanCount = data.scan_count || 0;
        state.baselineReady = data.baseline_ready || false;
        state.numNetworks = data.num_networks || 0;

        // Update HUD
        updateHUD();

        // Log state changes
        if (state.motionDetected && !prevMotion) {
            addLogEntry('motion', `🚨 MOTION DETECTED (${state.personCount} Person${state.personCount > 1 ? 's' : ''})`);
            showAlert(true);
        } else if (!state.motionDetected && prevMotion) {
            if (state.presenceDetected) {
                addLogEntry('presence', `👤 Static presence (${state.personCount} Person${state.personCount > 1 ? 's' : ''})`);
            } else {
                addLogEntry('clear', '✅ Area clear');
            }
            showAlert(false);
        }

        prevMotionState = state.motionDetected;

    } catch (error) {
        setConnected(false);
    }
}

// ═══════════════════════════════════════════════════════════════
//  HUD UPDATES
// ═══════════════════════════════════════════════════════════════
function updateHUD() {
    // Status text & indicator
    const indicator = document.getElementById('detection-indicator');
    const statusText = document.getElementById('status-text');

    if (state.motionDetected) {
        indicator.className = 'stat-indicator motion';
        statusText.textContent = 'MOTION';
        statusText.style.color = '#ff3366';
    } else if (state.presenceDetected) {
        indicator.className = 'stat-indicator presence';
        statusText.textContent = 'PRESENCE';
        statusText.style.color = '#ff8800';
    } else {
        indicator.className = 'stat-indicator clear';
        statusText.textContent = 'CLEAR';
        statusText.style.color = '#00ff88';
    }

    // Intensity bar
    const pct = Math.round(state.motionIntensity * 100);
    document.getElementById('intensity-fill').style.width = `${pct}%`;
    document.getElementById('intensity-value').textContent = `${pct}%`;

    // Confidence
    document.getElementById('confidence-text').textContent =
        `${Math.round(state.confidence * 100)}%`;

    // Networks
    document.getElementById('networks-text').textContent = state.numNetworks;

    // Scan count
    document.getElementById('scan-count').textContent = state.scanCount;

    // Baseline status
    const baselineEl = document.getElementById('baseline-status');
    if (state.baselineReady) {
        baselineEl.textContent = '✅ BASELINE READY';
        baselineEl.className = 'baseline-status ready';
    } else {
        baselineEl.textContent = '⏳ COLLECTING BASELINE...';
        baselineEl.className = 'baseline-status';
    }

    // Signals panel
    updateSignalPanel();

    // Mini radar position
    updateMiniRadar();
}

function updateSignalPanel() {
    const container = document.getElementById('signal-list');
    const countEl = document.getElementById('ap-count');

    countEl.textContent = `${state.signals.length} APs`;

    if (!state.signals.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:#446688;font-size:0.7rem;">Scanning...</div>';
        return;
    }

    // Sort by signal strength
    const sorted = [...state.signals].sort((a, b) => (b.rssi || -100) - (a.rssi || -100));

    container.innerHTML = sorted.slice(0, 12).map(sig => {
        const pct = sig.signal_percent || 0;
        const isHighVar = (sig.variance || 0) > 1.8;

        return `
            <div class="signal-item ${isHighVar ? 'high-variance' : ''}">
                <div class="signal-name">${sig.ssid || 'Hidden'}</div>
                <div class="signal-meta">
                    <div class="signal-bar-bg">
                        <div class="signal-bar-fg" style="width:${pct}%"></div>
                    </div>
                    <span class="signal-dbm">${sig.rssi} dBm</span>
                </div>
                <span class="signal-variance ${isHighVar ? 'active' : ''}">σ ${sig.variance || 0}</span>
            </div>
        `;
    }).join('');
}

function updateMiniRadar() {
    const dot = document.getElementById('mini-radar-dot');
    const posX = document.getElementById('pos-x');
    const posZ = document.getElementById('pos-z');

    if (state.motionDetected || state.presenceDetected) {
        dot.classList.add('visible');
        // Map position to mini radar (40px radius from center)
        const px = 50 + state.personPos.x * 35;
        const py = 50 + state.personPos.z * 35;
        dot.style.left = `${px}%`;
        dot.style.top = `${py}%`;
    } else {
        dot.classList.remove('visible');
    }

    posX.textContent = state.personPos.x.toFixed(2);
    posZ.textContent = state.personPos.z.toFixed(2);
}

// ═══════════════════════════════════════════════════════════════
//  CONNECTION STATUS
// ═══════════════════════════════════════════════════════════════
function setConnected(connected) {
    state.connected = connected;
    const el = document.getElementById('connection-status');

    if (connected) {
        el.className = 'hud-connection connected';
        el.querySelector('span').textContent = 'CONNECTED';
    } else {
        el.className = 'hud-connection';
        el.querySelector('span').textContent = 'DISCONNECTED';
    }
}

// ═══════════════════════════════════════════════════════════════
//  DETECTION ALERT
// ═══════════════════════════════════════════════════════════════
function showAlert(show) {
    const el = document.getElementById('detection-alert');
    if (show) {
        el.classList.add('visible');
        setTimeout(() => el.classList.remove('visible'), 3000);
    } else {
        el.classList.remove('visible');
    }
}

// ═══════════════════════════════════════════════════════════════
//  LOG
// ═══════════════════════════════════════════════════════════════
function addLogEntry(type, message) {
    const now = new Date();
    const time = now.toTimeString().slice(0, 8);

    logEntries.unshift({ type, message, time });
    if (logEntries.length > 20) logEntries.pop();

    const container = document.getElementById('detection-log');
    container.innerHTML = logEntries.map(e => `
        <div class="log-entry ${e.type}">
            <span class="log-time">${e.time}</span>
            <span class="log-msg">${e.message}</span>
        </div>
    `).join('');
}

// ═══════════════════════════════════════════════════════════════
//  UI EVENTS
// ═══════════════════════════════════════════════════════════════
function setupUIEvents() {
    document.getElementById('btn-reset').addEventListener('click', async () => {
        await fetch(`${CONFIG.api}/api/radar/reset`, { method: 'POST' });
        addLogEntry('system', '🔄 Baseline reset');
    });

    document.getElementById('btn-toggle-waves').addEventListener('click', () => {
        showWaves = !showWaves;
        document.getElementById('btn-toggle-waves').classList.toggle('active', showWaves);
    });
    document.getElementById('btn-toggle-waves').classList.add('active');

    document.getElementById('btn-toggle-grid').addEventListener('click', () => {
        showGrid = !showGrid;
        floorGrid.visible = showGrid;
        document.getElementById('btn-toggle-grid').classList.toggle('active', showGrid);
    });
    document.getElementById('btn-toggle-grid').classList.add('active');
}

// ═══════════════════════════════════════════════════════════════
//  RESIZE
// ═══════════════════════════════════════════════════════════════
function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

// ═══════════════════════════════════════════════════════════════
//  START
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', init);
