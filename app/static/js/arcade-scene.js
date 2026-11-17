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

/** Discreet procedural grain on the stone colour + optional fade to transparent with distance. */
function stoneShader(material, { fade = null } = {}) {
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
diffuseColor.rgb *= 0.9 + 0.14 * grain;`)
      .replace("#include <fog_fragment>", `#include <fog_fragment>
if (uFade.y > 0.0) gl_FragColor.a *= 1.0 - smoothstep(uFade.x, uFade.y, distance(vWPos, cameraPosition));`);
  };
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

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
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
    depth: DEPTH, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 2, curveSegments: 28,
  });
  disposables.push(bayGeometry);
  const bays = [];
  for (let i = 0; i < BAYS; i++) {
    const material = stoneShader(new THREE.MeshStandardMaterial({
      color: colors.stone, roughness: 0.92, metalness: 0, transparent: true, opacity: 0,
    }));
    const mesh = new THREE.Mesh(bayGeometry, material);
    mesh.rotation.y = Math.PI / 2;               // shape X runs along -Z, extrusion along +X
    mesh.position.set(-DEPTH, 0, START_Z - (i + 0.5) * BAY);
    mesh.castShadow = false;                      // switched on once the bay is half visible
    mesh.receiveShadow = true;
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
  box(DEPTH + 0.24, 0.62, span, entablature, -DEPTH / 2, WALL_TOP + 0.31, spanZ);
  box(DEPTH + 0.5, 0.16, span, entablature, -DEPTH / 2, WALL_TOP + 0.7, spanZ);

  // Ceiling (keeps the sun out from above), back wall, and a floor that dissolves into the hero.
  const shellLength = SHELL_NEAR + LENGTH + 12;
  const shellZ = SHELL_NEAR - shellLength / 2;
  const fade = [LENGTH * 0.75, LENGTH * 1.4];
  box(GALLERY + 0.6, 0.2, shellLength, stone(colors.inkSoft, { fade, params: { transparent: true } }),
    GALLERY / 2 - 0.3, WALL_TOP + 0.72, shellZ, { cast: true, receive: false });
  box(0.5, WALL_TOP + 0.8, shellLength, stone(colors.stoneDark, { fade, params: { transparent: true } }),
    GALLERY + 0.25, (WALL_TOP + 0.8) / 2, shellZ, { cast: false });
  const floorGeometry = new THREE.PlaneGeometry(80, shellLength);
  disposables.push(floorGeometry);
  const floor = new THREE.Mesh(floorGeometry, stone(colors.stoneDark, { fade, params: { transparent: true } }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(-20, 0, shellZ);
  floor.receiveShadow = true;
  scene.add(floor);
  await yieldThread();

  // ---- Light: faint sky, warm low sun with soft shadows ------------------------------------
  scene.add(new THREE.HemisphereLight(colors.inkSoft.clone().lerp(colors.brass, 0.25), colors.ink, 0.45));
  const sun = new THREE.DirectionalLight(colors.brass, 2.5);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.radius = 4;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.03;
  Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 24, bottom: -24, near: 1, far: 120 });
  const sunCenter = new THREE.Vector3(GALLERY / 2, 0, START_Z - LENGTH * 0.45);
  sun.target.position.copy(sunCenter);
  scene.add(sun, sun.target);

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
      mesh.castShadow = p > 0.5;
    });
    entablature.opacity = ease(elapsed / INTRO_MS);
    if (elapsed >= INTRO_MS) {
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
