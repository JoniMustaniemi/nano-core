/* global THREE */

const GLOBE_STATES = {
  standby: {
    speed: 0.32,
    breathe: 0.38,
    glow: 0.68,
    spread: 0.9,
    ripple: 0.28,
    chaos: 0.55,
    embers: 0.45,
    core: 0.72,
  },
  working: {
    speed: 0.95,
    breathe: 0.95,
    glow: 1.0,
    spread: 1.0,
    ripple: 0.72,
    chaos: 1.0,
    embers: 1.0,
    core: 1.0,
  },
  listening: {
    speed: 0.5,
    breathe: 0.62,
    glow: 0.96,
    spread: 1.06,
    ripple: 0.42,
    chaos: 0.78,
    embers: 0.72,
    core: 0.92,
  },
  speaking: {
    speed: 0.68,
    breathe: 1.35,
    glow: 1.0,
    spread: 1.03,
    ripple: 0.78,
    chaos: 0.92,
    embers: 0.82,
    core: 1.12,
  },
  reconnecting: {
    speed: 0.1,
    breathe: 0.12,
    glow: 0.28,
    spread: 0.72,
    ripple: 0.12,
    chaos: 0.25,
    embers: 0.15,
    core: 0.3,
  },
};

const STATE_COLORS = {
  standby: {
    primary: [0.03, 0.24, 0.09],
    secondary: [0.14, 0.88, 0.36],
  },
  working: {
    primary: [0.28, 0.20, 0.04],
    secondary: [1.0, 0.76, 0.15],
  },
  listening: {
    primary: [0.02, 0.28, 0.15],
    secondary: [0.12, 0.96, 0.74],
  },
  speaking: {
    primary: [0.04, 0.26, 0.07],
    secondary: [0.52, 0.98, 0.30],
  },
  reconnecting: {
    primary: [0.08, 0.14, 0.09],
    secondary: [0.20, 0.36, 0.22],
  },
};

function shaderParamsForState(state) {
  const globe = GLOBE_STATES[state] || GLOBE_STATES.standby;
  const colors = STATE_COLORS[state] || STATE_COLORS.standby;
  const energyStrength = globe.chaos * 0.55 + globe.embers * 0.45;

  return {
    color: [...colors.primary],
    secondaryColor: [...colors.secondary],
    energySpeed: 0.18 + globe.speed * 0.72,
    energyStrength: 0.22 + energyStrength * 0.58,
    glow: globe.glow,
    radiusScale: 0.44 + globe.spread * 0.05 + globe.core * 0.03,
  };
}

function lerpRgb(current, target, blend) {
  const t = Math.max(0, Math.min(1, blend));
  return current.map((value, index) => value + (target[index] - value) * t);
}

function lerpShaderParams(current, target, blend) {
  const t = Math.max(0, Math.min(1, blend));
  const mixFloat = (key) => current[key] + (target[key] - current[key]) * t;

  return {
    color: lerpRgb(current.color, target.color, t),
    secondaryColor: lerpRgb(current.secondaryColor, target.secondaryColor, t),
    energySpeed: mixFloat("energySpeed"),
    energyStrength: mixFloat("energyStrength"),
    glow: mixFloat("glow"),
    radiusScale: mixFloat("radiusScale"),
  };
}

const ORB_VERTEX_SHADER = `
varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const ORB_FRAGMENT_SHADER = `
precision highp float;

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_audio_level;
uniform vec3 u_color;
uniform vec3 u_secondary_color;
uniform float u_energy_time;
uniform float u_energy_strength;
uniform float u_glow;
uniform float u_radius_scale;

varying vec2 vUv;

float hash31(vec3 p) {
  p = fract(p * 0.1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}

float noise3d(vec3 p) {
  vec3 cell = floor(p);
  vec3 local = fract(p);
  local = local * local * (3.0 - 2.0 * local);

  float n000 = hash31(cell + vec3(0.0, 0.0, 0.0));
  float n100 = hash31(cell + vec3(1.0, 0.0, 0.0));
  float n010 = hash31(cell + vec3(0.0, 1.0, 0.0));
  float n110 = hash31(cell + vec3(1.0, 1.0, 0.0));
  float n001 = hash31(cell + vec3(0.0, 0.0, 1.0));
  float n101 = hash31(cell + vec3(1.0, 0.0, 1.0));
  float n011 = hash31(cell + vec3(0.0, 1.0, 1.0));
  float n111 = hash31(cell + vec3(1.0, 1.0, 1.0));

  float nx00 = mix(n000, n100, local.x);
  float nx10 = mix(n010, n110, local.x);
  float nx01 = mix(n001, n101, local.x);
  float nx11 = mix(n011, n111, local.x);
  float nxy0 = mix(nx00, nx10, local.y);
  float nxy1 = mix(nx01, nx11, local.y);

  return mix(nxy0, nxy1, local.z);
}

float fbm(vec3 p) {
  float value = 0.0;
  float amplitude = 0.5;
  for (int i = 0; i < 5; i++) {
    value += noise3d(p) * amplitude;
    p = p * 2.03 + vec3(17.1, 9.2, 13.7);
    amplitude *= 0.5;
  }
  return value;
}

mat2 rotate2d(float angle) {
  float c = cos(angle);
  float s = sin(angle);
  return mat2(c, -s, s, c);
}

vec3 rotateAxis(vec3 v, vec3 axis, float angle) {
  vec3 a = normalize(axis);
  float c = cos(angle);
  float s = sin(angle);
  return v * c + cross(a, v) * s + a * dot(a, v) * (1.0 - c);
}

float orbitRing3D(
  vec3 P,
  float zSphere,
  float radiusSquared,
  vec3 normalSeed,
  vec3 precessAxis,
  float ringRadius,
  float phase,
  float precessSpeed,
  float spinSpeed,
  float dashFreq,
  float lineWidth
) {
  vec3 n = rotateAxis(
    normalize(normalSeed),
    normalize(precessAxis),
    u_time * precessSpeed + phase
  );
  vec3 ref = abs(n.y) < 0.85 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
  vec3 u = normalize(cross(n, ref));
  vec3 v = cross(n, u);

  vec3 planePoint = P - n * dot(P, n);
  float distInPlane = length(planePoint);
  vec3 radial = distInPlane > 0.001 ? planePoint / distInPlane : u;
  vec3 closestOnRing = radial * ringRadius;

  float dist3d = length(P - closestOnRing);
  float lineMask = 1.0 - smoothstep(lineWidth * 0.12, lineWidth, dist3d);
  if (lineMask <= 0.0) {
    return 0.0;
  }

  if (radiusSquared < 1.0 && closestOnRing.z < zSphere - 0.025) {
    return 0.0;
  }

  float angle = atan(dot(closestOnRing, v), dot(closestOnRing, u)) + u_time * spinSpeed;
  float dash = sin(angle * dashFreq) * 0.5 + 0.5;
  dash = smoothstep(0.14, 0.62, dash);

  float frontFacing = smoothstep(-0.35, 0.45, closestOnRing.z);
  float depthFade = 0.55 + 0.45 * smoothstep(0.0, 0.8, closestOnRing.z + 0.35);

  return lineMask * dash * frontFacing * depthFade;
}

float orbitingRings3D(vec3 P, float zSphere, float radiusSquared) {
  float rings = 0.0;

  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(0.15, 0.92, 0.35), vec3(0.2, 1.0, 0.1), 1.12, 0.2, 0.42, 0.62, 3.5, 0.026);
  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(-0.55, 0.42, 0.72), vec3(-0.3, 0.8, 0.5), 1.24, 1.4, -0.34, -0.48, 4.2, 0.024);
  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(0.38, -0.62, 0.68), vec3(0.5, 0.2, 0.9), 1.36, 2.8, 0.28, 0.36, 5.0, 0.023);
  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(-0.22, 0.78, -0.58), vec3(0.1, 0.6, 1.0), 1.48, 4.2, -0.22, 0.52, 3.8, 0.022);
  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(0.72, -0.18, 0.52), vec3(-0.4, 0.3, 0.85), 1.60, 5.6, 0.46, -0.32, 6.0, 0.021);
  rings += orbitRing3D(P, zSphere, radiusSquared, vec3(-0.14, -0.36, 0.92), vec3(0.7, -0.2, 0.4), 1.72, 3.0, 0.18, 0.44, 4.5, 0.02);

  return clamp(rings, 0.0, 2.6);
}

vec3 orbitLineColor(vec3 base, vec3 accent) {
  return mix(base, accent, 0.45);
}

float silhouetteRingFade(float screenDistance) {
  return smoothstep(0.94, 1.02, screenDistance) * (1.0 - smoothstep(1.02, 1.12, screenDistance));
}

void main() {
  vec2 p = vUv * 2.0 - 1.0;
  float aspect = u_resolution.x / max(u_resolution.y, 1.0);
  p.x *= aspect;

  p = rotate2d(u_time * 0.035) * p;

  float audioExpansion = u_audio_level * 0.048;
  float radius = u_radius_scale + audioExpansion;

  vec2 sphereUv = p / radius;
  float radiusSquared = dot(sphereUv, sphereUv);
  float screenDistance = length(sphereUv);

  float outerGlow =
    exp(-max(screenDistance - 1.0, 0.0) * 7.0) *
    exp(-max(screenDistance - 1.0, 0.0) * 7.0);
  outerGlow *= smoothstep(1.42, 1.0, screenDistance);
  outerGlow *= (0.14 + u_audio_level * 0.22) * u_glow;

  vec3 viewDirection = vec3(0.0, 0.0, 1.0);
  float zSphere = sqrt(max(0.0, 1.0 - radiusSquared));
  vec3 scenePoint = vec3(sphereUv.x, sphereUv.y, 0.0);
  float surroundBoost = 0.85 + u_audio_level * 0.45;
  float ringSilhouetteFade = 1.0 - silhouetteRingFade(screenDistance);
  float surroundWaves = orbitingRings3D(scenePoint, zSphere, radiusSquared) * surroundBoost * ringSilhouetteFade;
  vec3 lineColor = orbitLineColor(u_secondary_color, vec3(0.28, 0.82, 0.42));
  float edgeSoftness = max(fwidth(radiusSquared) * 3.0, 0.0008);

  if (radiusSquared > 1.0) {
    vec3 haloColor = mix(u_color, u_secondary_color, 0.45) * outerGlow;
    haloColor += lineColor * surroundWaves * 1.45;
    float haloAlpha = clamp(max(outerGlow * 0.42, surroundWaves * 0.92), 0.0, 0.92);
    gl_FragColor = vec4(haloColor * haloAlpha, haloAlpha);
    return;
  }

  float z = zSphere;
  vec3 normal = normalize(vec3(sphereUv.x, sphereUv.y, z));
  vec3 lightDirection = normalize(vec3(-0.35, 0.45, 0.92));

  float diffuse = dot(normal, lightDirection) * 0.5 + 0.5;
  float fresnel = pow(1.0 - max(dot(normal, viewDirection), 0.0), 4.2);
  float rimMask = smoothstep(1.0, 0.82, radiusSquared);

  float animationTime = u_energy_time;
  vec3 energyPosition = normal * 3.2 + vec3(
    animationTime * 0.55,
    -animationTime * 0.72,
    animationTime * 0.38
  );

  float energy = fbm(energyPosition);
  float finerEnergy = fbm(
    normal * 7.0 +
    vec3(-animationTime * 1.05, animationTime * 0.62, animationTime * 0.7)
  );
  energy = mix(energy, finerEnergy, 0.30);

  float energyGlow = smoothstep(0.38, 0.72, energy);
  energyGlow *= u_energy_strength * 0.42;
  energyGlow *= 1.0 + u_audio_level * 0.9;

  float core = pow(z, 3.2);
  float depthShading = 0.35 + z * 0.65;

  vec3 deepColor = u_color * 0.12;
  vec3 surfaceColor = mix(deepColor, u_color, 0.22 + diffuse * 0.48);
  surfaceColor *= depthShading;

  surfaceColor = mix(surfaceColor, u_secondary_color, energy * 0.34);
  surfaceColor += u_secondary_color * energyGlow * 0.55;
  surfaceColor += mix(u_color, u_secondary_color, 0.6) * core * 0.18;
  surfaceColor += u_secondary_color * fresnel * rimMask * (0.18 + u_audio_level * 0.22) * u_glow;
  surfaceColor += u_color * outerGlow * 0.18;
  surfaceColor += lineColor * surroundWaves * 0.75;

  float sphereAlpha = 1.0 - smoothstep(1.0 - edgeSoftness, 1.0, radiusSquared);
  float ringAlpha = surroundWaves * 0.65;
  float alpha = clamp(max(sphereAlpha, max(outerGlow * 0.65, ringAlpha)), 0.0, 1.0);

  gl_FragColor = vec4(surfaceColor * alpha, alpha);
}
`;

function createOrbUniforms(params) {
  return {
    u_resolution: { value: new THREE.Vector2(1, 1) },
    u_time: { value: 0 },
    u_energy_time: { value: 0 },
    u_audio_level: { value: 0 },
    u_color: { value: new THREE.Vector3(...params.color) },
    u_secondary_color: { value: new THREE.Vector3(...params.secondaryColor) },
    u_energy_strength: { value: params.energyStrength },
    u_glow: { value: params.glow },
    u_radius_scale: { value: params.radiusScale },
  };
}

function smoothMotionParams(current, target, blend) {
  const t = Math.max(0, Math.min(1, blend));
  const mixFloat = (key) => current[key] + (target[key] - current[key]) * t;
  return {
    energySpeed: mixFloat("energySpeed"),
  };
}

class GlobeVisualizer {
  constructor(canvas, options = {}) {
    if (typeof THREE === "undefined") {
      throw new Error("Three.js is required for the essence orb.");
    }

    this.canvas = canvas;
    this.mini = Boolean(options.mini);
    this.state = "standby";
    this.target = shaderParamsForState("standby");
    this.current = shaderParamsForState("standby");
    this.time = 0;
    this.lastTs = 0;
    this.rafId = null;
    this.audioLevel = 0;
    this.targetAudioLevel = 0;
    this.audioPhase = 0;
    this.energyTime = 0;
    this.motion = {
      energySpeed: this.current.energySpeed,
    };
    this.useExternalAudio = false;
    this.width = 1;
    this.height = 1;

    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
      premultipliedAlpha: true,
    });
    this.renderer.setPixelRatio(this.mini ? Math.min(window.devicePixelRatio || 1, 2) : Math.min(window.devicePixelRatio || 1, 3));
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.autoClear = true;

    this.uniforms = createOrbUniforms(this.current);
    const material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: ORB_VERTEX_SHADER,
      fragmentShader: ORB_FRAGMENT_SHADER,
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.NormalBlending,
    });

    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    this.scene.add(this.mesh);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.resize();
    this.tick = this.tick.bind(this);
    this.rafId = requestAnimationFrame(this.tick);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = this.mini
      ? Math.min(window.devicePixelRatio || 1, 2)
      : Math.min(window.devicePixelRatio || 1, 3);
    this.width = Math.max(Math.round(rect.width * dpr), 1);
    this.height = Math.max(Math.round(rect.height * dpr), 1);
    this.renderer.setSize(this.width, this.height, false);
    this.uniforms.u_resolution.value.set(this.width, this.height);
  }

  setState(state) {
    this.state = state;
    this.target = shaderParamsForState(state);
  }

  setAudioLevel(level) {
    const clamped = Math.max(0, Math.min(1, level));
    this.targetAudioLevel = clamped;
    this.useExternalAudio = clamped > 0.01;
  }

  _updateAudioTarget(dt) {
    if (this.useExternalAudio) {
      if (this.targetAudioLevel <= 0.01) {
        this.useExternalAudio = false;
      } else {
        return;
      }
    }

    if (this.state === "listening") {
      this.audioPhase += dt * 3.2;
      const raw =
        0.08 +
        (0.5 + 0.5 * Math.sin(this.audioPhase)) * 0.18 +
        (0.5 + 0.5 * Math.sin(this.audioPhase * 2.1 + 0.8)) * 0.08;
      this.targetAudioLevel = Math.min(1, raw);
      return;
    }

    this.targetAudioLevel = 0;
  }

  _applyUniforms(params) {
    this.uniforms.u_color.value.set(params.color[0], params.color[1], params.color[2]);
    this.uniforms.u_secondary_color.value.set(
      params.secondaryColor[0],
      params.secondaryColor[1],
      params.secondaryColor[2],
    );
    this.uniforms.u_energy_strength.value = params.energyStrength;
    this.uniforms.u_glow.value = params.glow;

    let radiusScale = params.radiusScale;
    if (this.mini) {
      radiusScale *= 0.92;
    }
    this.uniforms.u_radius_scale.value = radiusScale;
  }

  tick(timestamp) {
    const rawDt = this.lastTs ? (timestamp - this.lastTs) / 1000 : 1 / 60;
    const dt = Math.min(0.033, Math.max(0.001, rawDt));
    this.lastTs = timestamp;
    this.time += dt;
    this._updateAudioTarget(dt);

    const colorBlend = 1 - Math.exp(-3.5 * dt);
    this.current = lerpShaderParams(this.current, this.target, colorBlend);

    const motionBlend = 1 - Math.exp(-1.8 * dt);
    this.motion = smoothMotionParams(this.motion, this.current, motionBlend);

    const audioBlend = 1 - Math.exp(-8 * dt);
    this.audioLevel += (this.targetAudioLevel - this.audioLevel) * audioBlend;

    this.energyTime += dt * this.motion.energySpeed;

    this.uniforms.u_time.value = this.time;
    this.uniforms.u_energy_time.value = this.energyTime;
    this.uniforms.u_audio_level.value = this.audioLevel;
    this._applyUniforms(this.current);

    this.renderer.render(this.scene, this.camera);
    this.rafId = requestAnimationFrame(this.tick);
  }

  destroy() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
    }
    this.resizeObserver.disconnect();
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.renderer.dispose();
  }
}

function initEssenceOrbs() {
  if (typeof THREE === "undefined") {
    console.error("Three.js failed to load. Essence orb unavailable.");
    return;
  }

  const canvases = [
    { node: document.getElementById("globe-canvas"), mini: false, key: "main" },
    { node: document.getElementById("globe-mini-canvas"), mini: true, key: "mini" },
  ];

  for (const entry of canvases) {
    if (!entry.node) {
      continue;
    }
    try {
      const globe = new GlobeVisualizer(entry.node, { mini: entry.mini });
      if (entry.key === "main") {
        window.mainGlobe = globe;
      } else {
        window.miniGlobe = globe;
      }
    } catch (error) {
      console.error(`Failed to initialize ${entry.key} essence orb:`, error);
    }
  }
}

window.initEssenceOrbs = initEssenceOrbs;
