/* Ymmo — the 3D stone gallery of the home hero (Three.js).
 *
 * No DOM access here: this module runs either in a Web Worker on an OffscreenCanvas (preferred,
 * keeps the main thread free) or on the main thread as a fallback. hero-arcade.js owns the
 * page: it measures the layout, reads the colour tokens and forwards pointer / scroll input.
 *
 * Scene: a gallery seen from inside. Arcade wall on the left (x in [-D, 0]), back wall on the
 * right (x = G), bays receding towards -Z. A low late-afternoon sun outside the arcade (-X side)
 * shines through the openings and draws their shapes on the floor and on the back wall.
 */

// Vendored, tree-shaken Three.js; reuse this module's cache-busting query (?v=ASSET_VERSION).
const THREE_URL = new URL(`../vendor/three/three.arcade.min.js${new URL(import.meta.url).search}`, import.meta.url).href;

const BAYS = 12;            // ~8 visible at once; the nearest ones sit outside the frame
const BAY = 3.4;            // bay length along the gallery
const PIER = 0.78;          // pier width
const RADIUS = (BAY - PIER) / 2;
const SPRING = 2.9;         // height where the arch starts
const WALL_TOP = 5.0;
const DEPTH = 0.9;          // wall thickness
const GALLERY = 4.8;        // gallery width (arcade to back wall)
const LENGTH = BAYS * BAY;
const START_Z = 17;         // first bays start outside the frame, on the left
const SHELL_NEAR = 30;      // ceiling, back wall and floor run on behind the camera

const INTRO_MS = 1200;
const INTRO_BAY_MS = 650;
const SUN_LOOP_MS = 20000;

const CAMERA = { x: 2.3, y: 1.2, wideZ: 11, narrowZ: 18 }; // narrow: further back for a short strip
const UPWARD_DEG = 5;       // slight worm's-eye view

const frame = (callback) => (typeof requestAnimationFrame === "function"
  ? requestAnimationFrame(callback)
  : setTimeout(() => callback(performance.now()), 16));
const cancelFrame = (id) => (typeof cancelAnimationFrame === "function" ? cancelAnimationFrame(id) : clearTimeout(id));

/** Gives the thread back between setup steps, so no single task runs for long. */
const yieldThread = () => new Promise((resolve) => {
  if (globalThis.scheduler?.yield) globalThis.scheduler.yield().then(resolve);
  else setTimeout(resolve, 0);
});

/** cubic-bezier(x1, y1, x2, y2) easing, same curve as the CSS token --ease. */
function cubicBezier(x1, y1, x2, y2) {
  const ax = 3 * x1 - 3 * x2 + 1, bx = 3 * x2 - 6 * x1, cx = 3 * x1;
  const ay = 3 * y1 - 3 * y2 + 1, by = 3 * y2 - 6 * y1, cy = 3 * y1;
  const sx = (t) => ((ax * t + bx) * t + cx) * t;
  const sy = (t) => ((ay * t + by) * t + cy) * t;
  const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
  return (x) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 6; i++) {
      const err = sx(t) - x;
      const d = dx(t);
      if (Math.abs(err) < 1e-5 || Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    return sy(Math.min(1, Math.max(0, t)));
  };
}
const ease = cubicBezier(0.2, 0.7, 0.2, 1);

/**
 * Stone look: discreet procedural grain, painted ambient occlusion (darker where surfaces meet:
 * foot of the piers, under the entablement, along the back wall) and an optional fade to
 * transparent with distance. `ao`: "wall" (by height) or "floor" (by distance to the walls).
 */
const AO = {
  wall: `float ao = mix(0.6, 1.0, smoothstep(0.0, 1.2, vWPos.y));
ao *= 1.0 - 0.22 * smoothstep(${(WALL_TOP - 0.9).toFixed(2)}, ${WALL_TOP.toFixed(2)}, vWPos.y);`,
  // Back wall: also deep shade where it meets the ceiling (hides the thin shadow-map leak there).
  backWall: `float ao = mix(0.6, 1.0, smoothstep(0.0, 1.2, vWPos.y));
ao *= 1.0 - 0.6 * smoothstep(${(WALL_TOP - 0.6).toFixed(2)}, ${(WALL_TOP + 0.3).toFixed(2)}, vWPos.y);
ao *= 1.0 - smoothstep(${(WALL_TOP + 0.3).toFixed(2)}, ${(WALL_TOP + 0.58).toFixed(2)}, vWPos.y);`,
  floor: `float ao = mix(0.55, 1.0, smoothstep(0.0, 1.4, abs(vWPos.x - ${GALLERY.toFixed(2)})));
ao *= mix(0.78, 1.0, smoothstep(0.0, 0.9, vWPos.x));`,
};
function stoneShader(material, { fade = null, ao = null } = {}) {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uFade = { value: fade || [0, 0] };
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vWPos;")
      .replace("#include <project_vertex>", "#include <project_vertex>\nvWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>
varying vec3 vWPos;
uniform vec2 uFade;
float yHash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float yNoise(vec3 x) {
  vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(yHash(i), yHash(i + vec3(1,0,0)), f.x), mix(yHash(i + vec3(0,1,0)), yHash(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(yHash(i + vec3(0,0,1)), yHash(i + vec3(1,0,1)), f.x), mix(yHash(i + vec3(0,1,1)), yHash(i + vec3(1,1,1)), f.x), f.y), f.z);
}`)
      .replace("#include <color_fragment>", `#include <color_fragment>
float grain = yNoise(vWPos * 1.3) * 0.6 + yNoise(vWPos * 6.0) * 0.4;
diffuseColor.rgb *= 0.9 + 0.14 * grain;
${ao ? `${AO[ao]}
diffuseColor.rgb *= ao;` : ""}`)
      // Occlusion also dims the sun's specular (it would otherwise outline the shadow edges).
      .replace("#include <aomap_fragment>", `#include <aomap_fragment>
${ao ? "reflectedLight.directSpecular *= ao; reflectedLight.indirectSpecular *= ao;" : ""}`)
      .replace("#include <fog_fragment>", `#include <fog_fragment>
if (uFade.y > 0.0) gl_FragColor.a *= 1.0 - smoothstep(uFade.x, uFade.y, distance(vWPos, cameraPosition));`);
  };
  // Three caches programs by onBeforeCompile's source, identical for every stone: without its own
  // key, each occlusion variant would reuse whichever program compiled first.
  material.customProgramCacheKey = () => `stone-${ao || "none"}`;
  return material;
}

/** One bay: two half piers + an arch, as a single outline (extruded with a light bevel). */
function bayShape(THREE) {
  const half = BAY / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-half, 0);
  shape.lineTo(-half, WALL_TOP);
  shape.lineTo(half, WALL_TOP);
  shape.lineTo(half, 0);
  shape.lineTo(RADIUS, 0);
  shape.lineTo(RADIUS, SPRING);
  shape.absarc(0, SPRING, RADIUS, 0, Math.PI, false);
  shape.lineTo(-RADIUS, 0);
  shape.lineTo(-half, 0);
  return shape;
}

/**
 * Builds the scene on `canvas` (HTMLCanvasElement or OffscreenCanvas) and renders a first frame.
 * Returns null when WebGL is unavailable. The returned controller accepts messages:
 *   {type: "resize", view: {width, height, narrow, horizon}}  horizon: fraction of the height or null
 *   {type: "pointer", x, y}   normalised -1..1      {type: "scroll", progress}   0..1
 *   {type: "run", on}         start / stop the loop
 */
export async function createArcade(canvas, { colors: palette, dpr, view: initialView, onLost }) {
  const THREE = await import(THREE_URL);
  await yieldThread();

  // Ask for the WebGL 2 context first: without it, quietly keep the SVG (Three.js would log an
  // error to the console when it fails to create one itself).
  const attributes = { alpha: true, antialias: true, powerPreference: "low-power" };
  let renderer;
  try {
    const context = canvas.getContext("webgl2", attributes);
    if (!context) return null;
    renderer = new THREE.WebGLRenderer({ canvas, context, ...attributes });
  } catch {
    return null;
  }
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(dpr);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap; // PCFSoftShadowMap was folded into PCFShadowMap in r18x

  const colors = Object.fromEntries(Object.entries(palette).map(([key, hex]) => [key, new THREE.Color(hex)]));
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(colors.ink, 0.034);
  const disposables = [];

  // ---- Arches: one extruded bay each, so they can appear one after the other ---------------
  const bayGeometry = new THREE.ExtrudeGeometry(bayShape(THREE), {
    depth: DEPTH, bevelEnabled: true, bevelThickness: 0.035, bevelSize: 0.035, bevelSegments: 3, curveSegments: 32,
  });
  disposables.push(bayGeometry);
  // Mouldings of the two half piers of a bay, in the bay's own frame (shape X/Y, extrusion Z):
  // a stepped plinth at the foot and an impost (capital) where the arch springs. Neighbouring
  // bays complete each other, so every pier gets a full moulding; children fade with their bay.
  const half = BAY / 2;
  const mouldingSpecs = [
    { overhang: 0.09, height: 0.42, y: 0.21 },                // plinth
    { overhang: 0.05, height: 0.12, y: 0.48 },                // plinth top step
    { overhang: 0.03, height: 0.07, y: SPRING - 0.2 },        // astragal
    { overhang: 0.11, height: 0.16, y: SPRING - 0.06 },       // impost slab
  ];
  const mouldings = mouldingSpecs.map(({ overhang, height, y }) => {
    const width = PIER / 2 + overhang;
    const geometry = new THREE.BoxGeometry(width, height, DEPTH + 2 * overhang);
    disposables.push(geometry);
    return { geometry, y, x: half - width / 2 };
  });
  const bays = [];
  for (let i = 0; i < BAYS; i++) {
    const material = stoneShader(new THREE.MeshStandardMaterial({
      color: colors.stone, roughness: 0.92, metalness: 0, transparent: true, opacity: 0,
    }), { ao: "wall" });
    const mesh = new THREE.Mesh(bayGeometry, material);
    mesh.rotation.y = Math.PI / 2;               // shape X runs along -Z, extrusion along +X
    mesh.position.set(-DEPTH, 0, START_Z - (i + 0.5) * BAY);
    mesh.castShadow = false;                      // switched on once the bay is half visible
    mesh.receiveShadow = true;
    for (const { geometry, y, x } of mouldings) {
      for (const side of [-1, 1]) {
        const part = new THREE.Mesh(geometry, material);
        part.position.set(side * x, y, DEPTH / 2);
        part.receiveShadow = true;
        mesh.add(part);
      }
    }
    scene.add(mesh);
    bays.push(mesh);
    disposables.push(material);
  }

  const stone = (color, extra = {}) => {
    const material = stoneShader(
      new THREE.MeshStandardMaterial({ color, roughness: 0.95, metalness: 0, ...extra.params }), extra,
    );
    disposables.push(material);
    return material;
  };
  const box = (w, h, d, material, x, y, z, { cast = true, receive = true } = {}) => {
    const geometry = new THREE.BoxGeometry(w, h, d);
    disposables.push(geometry);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.castShadow = cast;
    mesh.receiveShadow = receive;
    scene.add(mesh);
    return mesh;
  };

  // Continuous entablement (architrave + cornice), fades in with the arches.
  const entablature = stone(colors.stone, { params: { transparent: true, opacity: 0 } });
  const span = LENGTH + 0.2;
  const spanZ = START_Z - LENGTH / 2;
  // Wall, architrave, cornice and ceiling all overlap a little: with touching faces the sun
  // slipped through the seams and drew thin lines of light on the back wall.
  box(DEPTH + 0.24, 0.84, span, entablature, -DEPTH / 2, WALL_TOP + 0.30, spanZ);
  box(DEPTH + 0.5, 0.2, span, entablature, -DEPTH / 2, WALL_TOP + 0.68, spanZ);

  // Ceiling (keeps the sun out from above), back wall, and a floor that dissolves into the hero.
  const shellLength = SHELL_NEAR + LENGTH + 12;
  const shellZ = SHELL_NEAR - shellLength / 2;
  const fade = [LENGTH * 0.75, LENGTH * 1.4];
  // The ceiling runs from the outer face of the arcade to the outside of the back wall, so no
  // sliver of sun gets in between them.
  const ceilingLeft = -DEPTH - 0.3;
  const ceilingRight = GALLERY + 0.5;
  // shadowSide: both faces go into the shadow map. With the default (back faces only) the top of
  // the back wall, tucked inside the ceiling, was seen as lit and drew a bright line in the corner.
  const ceiling = stone(colors.inkSoft, { fade, params: { transparent: true, shadowSide: THREE.DoubleSide } });
  box(ceilingRight - ceilingLeft, 0.6, shellLength, ceiling,
    (ceilingLeft + ceilingRight) / 2, WALL_TOP + 0.92, shellZ, { cast: true, receive: false });
  box(0.5, WALL_TOP + 1.1, shellLength, stone(colors.stoneDark, { fade, ao: "backWall", params: { transparent: true } }),
    GALLERY + 0.25, (WALL_TOP + 1.1) / 2, shellZ, { cast: false });
  const floorGeometry = new THREE.PlaneGeometry(80, shellLength);
  disposables.push(floorGeometry);
  const floor = new THREE.Mesh(floorGeometry, stone(colors.stoneDark, { fade, ao: "floor", params: { transparent: true } }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(-20, 0, shellZ);
  floor.receiveShadow = true;
  scene.add(floor);
  await yieldThread();

  // ---- Light: faint sky, warm low sun with soft shadows ------------------------------------
  scene.add(new THREE.HemisphereLight(colors.inkSoft.clone().lerp(colors.brass, 0.25), colors.ink, 0.45));
  const sun = new THREE.DirectionalLight(colors.brass, 2.5);
  sun.castShadow = true;
  // The shadow map only covers the gallery (refitted as the sun moves, see fitShadow), so its
  // texels stay small and the arch shadows have clean edges instead of stair steps.
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 2;
  sun.shadow.bias = -0.0002;
  sun.shadow.normalBias = 0.02;
  const sunCenter = new THREE.Vector3(GALLERY / 2, 0, START_Z - LENGTH * 0.45);
  sun.target.position.copy(sunCenter);
  scene.add(sun, sun.target);

  // Shadow camera = tight box around the gallery, in the light's own frame (same basis as
  // DirectionalLightShadow: looking from the sun to its target).
  const shadowBox = [];
  for (const x of [-DEPTH - 0.4, GALLERY + 0.6]) {
    for (const y of [0, WALL_TOP + 0.9]) {
      for (const z of [START_Z + 0.5, START_Z - LENGTH - 0.5]) shadowBox.push(new THREE.Vector3(x, y, z));
    }
  }
  const UP = new THREE.Vector3(0, 1, 0);
  const axisX = new THREE.Vector3();
  const axisY = new THREE.Vector3();
  const axisZ = new THREE.Vector3();
  const rel = new THREE.Vector3();
  function fitShadow() {
    axisZ.subVectors(sun.position, sun.target.position).normalize();
    axisX.crossVectors(UP, axisZ).normalize();
    axisY.crossVectors(axisZ, axisX);
    // Runs every frame: plain scalars, no per-corner allocation.
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    let minD = Infinity, maxD = -Infinity;
    for (const point of shadowBox) {
      rel.subVectors(point, sun.position);
      const x = rel.dot(axisX), y = rel.dot(axisY), d = -rel.dot(axisZ);
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      minD = Math.min(minD, d); maxD = Math.max(maxD, d);
    }
    Object.assign(sun.shadow.camera, {
      left: minX - 0.5, right: maxX + 0.5, bottom: minY - 0.5, top: maxY + 0.5,
      near: Math.max(0.5, minD - 2), far: maxD + 2,
    });
    sun.shadow.camera.updateProjectionMatrix();
  }

  // ---- Light in the air: a faint additive sheet of sunlight through each arch, and a warm
  // glow at the vanishing point that draws the eye down the gallery ---------------------------
  const BEAM_OPACITY = 0.14;
  const GLOW_OPACITY = 0.55;
  const glowShader = (material, alpha) => {
    material.onBeforeCompile = (shader) => {
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec2 vLightUv;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\nvLightUv = uv;");
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", "#include <common>\nvarying vec2 vLightUv;")
        .replace("#include <color_fragment>", `#include <color_fragment>\n${alpha}`);
    };
    material.customProgramCacheKey = () => `glow-${alpha}`;
    disposables.push(material);
    return material;
  };
  const additive = (fog) => new THREE.MeshBasicMaterial({
    color: colors.amber, transparent: true, opacity: 0, blending: THREE.AdditiveBlending,
    depthWrite: false, side: THREE.DoubleSide, fog,
  });
  // uv.x: 0 at the opening -> 1 on the back wall; uv.y: 0 at the floor -> 1 under the arch.
  const beamMaterial = glowShader(additive(true), `diffuseColor.a *= pow(1.0 - vLightUv.x, 1.6)
  * smoothstep(0.0, 0.3, vLightUv.y) * smoothstep(1.0, 0.6, vLightUv.y) * smoothstep(0.0, 0.08, vLightUv.x);`);
  const beams = [];
  for (let i = 0; i < BAYS; i++) {
    const geometry = new THREE.PlaneGeometry(1, 1);
    disposables.push(geometry);
    const beam = new THREE.Mesh(geometry, beamMaterial);
    beam.frustumCulled = false; // vertices move every frame
    beam.renderOrder = 2;
    beam.userData.z = START_Z - (i + 0.5) * BAY;
    scene.add(beam);
    beams.push(beam);
  }
  const glowGeometry = new THREE.PlaneGeometry(GALLERY * 2.6, WALL_TOP * 1.7);
  disposables.push(glowGeometry);
  const glowMaterial = glowShader(additive(false), `float r = length((vLightUv - vec2(0.5, 0.42)) * vec2(1.0, 1.35)) * 2.0;
diffuseColor.a *= pow(max(0.0, 1.0 - r), 2.4);`);
  const glow = new THREE.Mesh(glowGeometry, glowMaterial);
  glow.position.set(GALLERY / 2, WALL_TOP * 0.45, START_Z - LENGTH - 0.6);
  glow.renderOrder = 2;
  scene.add(glow);

  let lightIn = 0; // 0..1, rises with the intro
  const travel = new THREE.Vector3();
  function updateBeams() {
    travel.copy(sunDirection).negate(); // direction the light travels
    const length = GALLERY / Math.max(0.2, travel.x); // from the inner face of the arcade to the back wall
    const top = SPRING + RADIUS * 0.75;
    for (const beam of beams) {
      const z = beam.userData.z;
      const position = beam.geometry.attributes.position;
      // PlaneGeometry vertex order: (u0,v1) (u1,v1) (u0,v0) (u1,v0)
      position.setXYZ(0, 0, top, z);
      position.setXYZ(1, travel.x * length, top + travel.y * length, z + travel.z * length);
      position.setXYZ(2, 0, 0.02, z);
      position.setXYZ(3, travel.x * length, 0.02 + travel.y * length, z + travel.z * length);
      position.needsUpdate = true;
    }
    beamMaterial.color.copy(sun.color);
    beamMaterial.opacity = BEAM_OPACITY * lightIn * (sun.intensity / 2.5);
    glowMaterial.color.copy(sun.color).lerp(colors.amber, 0.5);
    glowMaterial.opacity = GLOW_OPACITY * lightIn;
  }

  const sunDirection = new THREE.Vector3();
  const updateSun = (time) => {
    // The sun slowly sinks and rises again over ~20 s: elevation 7°..13°, slight azimuth drift.
    const wave = Math.sin(((time % SUN_LOOP_MS) / SUN_LOOP_MS) * Math.PI * 2);
    const elevation = THREE.MathUtils.degToRad(10 + 3 * wave);
    const azimuth = THREE.MathUtils.degToRad(48 + 4 * wave); // from -X towards +Z
    sunDirection.set(-Math.cos(azimuth) * Math.cos(elevation), Math.sin(elevation), Math.sin(azimuth) * Math.cos(elevation));
    sun.position.copy(sunCenter).addScaledVector(sunDirection, 60);
    sun.color.copy(colors.brass).lerp(colors.amber, 0.15 + ((1 - wave) / 2) * 0.45); // lower, warmer
    sun.intensity = 2.5 + wave * 0.4;
    fitShadow();
    updateBeams();
  };

  // ---- Camera: long lens, aimed so the vanishing point sits right of the title ---------------
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 140);
  camera.rotation.order = "YXZ";
  const rad = THREE.MathUtils.degToRad;
  const aim = { yaw: 0, pitch: rad(UPWARD_DEG), z: CAMERA.wideZ };
  let running = false;

  const resize = ({ width, height, narrow, horizon }) => {
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.fov = narrow ? 36 : 32;
    camera.updateProjectionMatrix();
    const halfV = Math.tan(rad(camera.fov / 2));
    // Vanishing point at (fx, fy) of the canvas.
    const fx = narrow ? 0.7 : (width < 560 ? 0.56 : 0.62);
    aim.yaw = Math.atan((2 * fx - 1) * halfV * camera.aspect);
    aim.pitch = narrow && horizon != null
      ? THREE.MathUtils.clamp(Math.atan((2 * horizon - 1) * halfV), rad(-6), rad(9))
      : rad(UPWARD_DEG);
    aim.z = narrow ? CAMERA.narrowZ : CAMERA.wideZ;
    if (!running) render(performance.now());
  };

  // ---- Input: pointer parallax (2.5° max) and scroll dolly, both eased --------------------
  const input = { x: 0, y: 0, scroll: 0 };
  const view = { yaw: 0, pitch: 0, dolly: 0 };

  // ---- Loop -------------------------------------------------------------------------------
  let introStart = -1;
  let introDone = false;
  let last = performance.now();
  let raf = 0;

  const animateIntro = (now) => {
    // Arches appear one by one, nearest first: fade + slight rise, 1.2 s in total.
    const elapsed = now - introStart;
    const stagger = (INTRO_MS - INTRO_BAY_MS) / (BAYS - 1);
    bays.forEach((mesh, i) => {
      const p = ease((elapsed - i * stagger) / INTRO_BAY_MS);
      mesh.material.opacity = p;
      mesh.position.y = -0.45 * (1 - p);
      const cast = p > 0.5;
      mesh.traverse((part) => { part.castShadow = cast; });
    });
    entablature.opacity = ease(elapsed / INTRO_MS);
    lightIn = ease(elapsed / INTRO_MS);
    if (elapsed >= INTRO_MS) {
      lightIn = 1;
      introDone = true;
      for (const material of [...bays.map((b) => b.material), entablature]) {
        material.opacity = 1;
        material.transparent = false;
        material.needsUpdate = true;
      }
    }
  };

  function render(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (introStart < 0) introStart = now;
    if (!introDone) animateIntro(now);
    updateSun(now);
    const k = 1 - Math.exp(-dt * 2.2);
    view.yaw += (-input.x * rad(2.5) - view.yaw) * k;
    view.pitch += (-input.y * rad(1.5) - view.pitch) * k;
    view.dolly += (input.scroll * 6 - view.dolly) * k;
    camera.position.set(CAMERA.x, CAMERA.y, aim.z - view.dolly);
    camera.rotation.set(aim.pitch + view.pitch, aim.yaw + view.yaw, 0);
    renderer.render(scene, camera);
  }

  const loop = (now) => {
    if (!running) return;
    render(now);
    raf = frame(loop);
  };
  const run = (on) => {
    if (on && !running) {
      running = true;
      last = performance.now();
      raf = frame(loop);
    } else if (!on && running) {
      running = false;
      cancelFrame(raf);
    }
  };

  const dispose = () => {
    run(false);
    disposables.forEach((item) => item.dispose());
    renderer.dispose();
  };

  const lost = (event) => {
    event.preventDefault?.();
    dispose();
    onLost?.();
  };
  canvas.addEventListener("webglcontextlost", lost, { once: true });
  canvas.addEventListener("contextlost", lost, { once: true }); // OffscreenCanvas

  // ---- Shaders: compiled off-thread when the GPU allows it, otherwise mesh by mesh --------
  resize(initialView);
  updateSun(0);
  if (renderer.extensions.has("KHR_parallel_shader_compile")) {
    await renderer.compileAsync(scene, camera);
  } else {
    const meshes = [];
    scene.traverse((object) => { if (object.isMesh) meshes.push(object); });
    for (const mesh of meshes) {
      await yieldThread();
      renderer.compile(mesh, camera, scene);
    }
  }
  await yieldThread();
  if (renderer.getContext().isContextLost()) {
    dispose();
    return null;
  }
  render(performance.now()); // first frame (intro starts at 0 opacity)

  return {
    handle(message) {
      if (message.type === "resize") resize(message.view);
      else if (message.type === "pointer") { input.x = message.x; input.y = message.y; }
      else if (message.type === "scroll") input.scroll = message.progress;
      else if (message.type === "run") run(message.on);
    },
    dispose,
  };
}
