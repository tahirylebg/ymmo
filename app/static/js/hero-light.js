/* Ymmo — the home hero's light: late-afternoon sun on a lime-washed wall.
 *
 * Purely decorative progressive enhancement, loaded on demand by app.js once the page is idle.
 * The poster (a still of this very shader, rendered by scripts/render_hero_poster.mjs) is in the
 * HTML and stays under the canvas: the canvas only fades in once its first frame is drawn (class
 * `has-light` on .hero-backdrop), picking up exactly where the poster is. Without JS or WebGL, with
 * reduced motion or data saver, if the context is lost or the device is too slow, the poster is
 * all there is.
 *
 * One full-screen fragment shader, raw WebGL (2, or 1), no library; drawn in a worker on an
 * OffscreenCanvas when the browser allows it (the module is its own worker), else right here.
 * The sun comes in through an arched, mullioned window out of frame and throws its shape on the
 * wall: a projective transform (homography) maps each wall point back into the window, where the
 * opening and its glazing bars are signed distance fields. The edge softness grows with the
 * distance from the window's base (penumbra). Leaf shadows (warped fbm) move inside the patch only,
 * a few dust motes drift in the beam, a fine film grain covers everything (and kills banding).
 */

const VERTEX = `
attribute vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FRAGMENT = `
precision highp float;
uniform vec2 uRes;        // drawing buffer, px
uniform float uTime;      // seconds
uniform float uLight;     // 0..1: scroll dimming
uniform float uWarm;      // 0..1: towards amber (scroll)
uniform float uGrain;
uniform float uBars;       // 1: the window's glazing bars; 0: a plain beam (the sell band)
uniform float uPx;        // one CSS pixel in wall units
uniform mat3 uH;          // wall -> window square (homogeneous)
uniform vec3 uInk, uInk2, uBrass, uAmber; // linear RGB

const float T = 2.25;     // window height / width (rectangle + half-circle top)
const float R = T - 0.5;  // springing line of the arch

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + 1.0), u.x), u.y);
}
float fbm(vec2 p) {
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { s += a * noise(p); p = p * 2.03 + vec2(17.1, 9.2); a *= 0.5; }
  return s;
}

// Window opening, width 1 (x 0..1), base at y = 0, round arch on top. Negative inside.
float sdOpening(vec2 q) {
  vec2 c = vec2(q.x - 0.5, q.y);
  if (c.y < R) return max(abs(c.x) - 0.5, -c.y);
  return length(c - vec2(0.0, R)) - 0.5;
}
// Glazing bars: the meeting stiles of the two leaves, three transoms (four panes per leaf),
// the springing bar and the fanlight's two spokes. Negative on a bar.
float sdBars(vec2 q) {
  float d = abs(q.x - 0.5) - 0.028;
  for (int k = 1; k < 4; k++) d = min(d, abs(q.y - R * float(k) / 4.0) - 0.016);
  d = min(d, abs(q.y - R) - 0.02);
  if (q.y > R) {
    vec2 c = q - vec2(0.5, R);
    d = min(d, abs(dot(c, vec2(0.7071, 0.7071))) - 0.014);
    d = min(d, abs(dot(c, vec2(0.7071, -0.7071))) - 0.014);
  }
  return d;
}

void main() {
  vec2 p = gl_FragCoord.xy / uRes.y;          // wall: y 0..1 up, x 0..aspect
  vec3 h = uH * vec3(p, 1.0);
  vec2 s = h.xy / h.z;                          // window square 0..1
  vec2 q = vec2(s.x, s.y * T);                  // window units
  float ahead = step(0.0, h.z);

  // Penumbra: sharp at the sill, wider and wider towards the top of the arch.
  float rise = clamp(q.y / T, 0.0, 1.0);
  float w = 0.012 + 0.03 * rise + 0.09 * rise * rise;
  float open = sdOpening(q);
  // The bars' shadows soften like the opening's edge (never quite sharp, even at the sill).
  float wb = max(w, 0.02) * 1.3;
  float bars = mix(1.0, smoothstep(-wb, wb, sdBars(q)), uBars);
  float light = smoothstep(w, -w, open) * bars * ahead;

  // Leaves: a branch outside the window, its shadow very soft (far from the wall), swaying
  // a few pixels, with rare slow gusts.
  float gust = pow(noise(vec2(uTime * 0.045, 3.7)), 3.0);
  vec2 sway = vec2(sin(uTime * 0.55) + 0.6 * sin(uTime * 0.93 + 1.3),
                   cos(uTime * 0.41) * 0.6) * uPx * (2.0 + 9.0 * gust);
  // Olive leaves: small, long and leaning, so the noise is stretched along a slant.
  vec2 lq = q + sway * 3.0;
  vec2 lp = mat2(0.80, -0.60, 0.60, 0.80) * lq * vec2(7.0, 2.6);
  vec2 warp = vec2(fbm(lq * 1.6 + vec2(0.0, uTime * 0.01)), fbm(lq * 1.6 + vec2(5.2, 1.3)));
  float foliage = fbm(lp + warp * 2.4);
  float branch = smoothstep(1.05, 0.45, s.x * 0.8 + (1.0 - s.y) * 1.1); // from the top left
  float soft = 0.05 + 0.06 * rise;
  float leaves = smoothstep(0.53 - soft, 0.53 + soft, foliage) * branch;

  // Wall: lime plaster, dark and warm; tone variations at large scale, a hint of trowel marks.
  float tone = fbm(p * vec2(2.2, 2.6));
  float trowel = fbm(p * vec2(38.0, 22.0) + tone * 2.0);
  vec3 wall = mix(uInk, uInk2, 0.25 + 0.55 * tone) * (0.94 + 0.12 * trowel);
  // The plaster catches the light more on its tiny reliefs.
  float relief = 0.95 + 0.1 * fbm(p * vec2(140.0, 120.0));

  // Light colour: amber at the heart of the patch, brass at its edges; warmer as one scrolls.
  float heart = smoothstep(0.75, 0.05, length((s - vec2(0.5, 0.42)) * vec2(1.0, 0.8)));
  vec3 sun = mix(uBrass, uAmber, heart * 0.7);
  sun = mix(sun, uAmber * vec3(1.0, 0.82, 0.62), uWarm);

  // Further from the sill, the light is spread wider: dimmer towards the arch, and it fades into
  // the wall rather than stopping like a cut-out.
  // A little unevenness across the panes (old glass), and a hotter heart.
  float spread = mix(1.0, 0.5, smoothstep(0.0, 1.0, rise)) * mix(0.66, 1.0, heart)
               * (0.9 + 0.1 * noise(q * 3.0));
  float patch = light * spread * (1.0 - 0.7 * leaves) * relief;
  // Soft bounce around the patch, and the air of the beam (very faint).
  float glow = smoothstep(0.9, -0.2, open) * ahead;
  vec3 col = wall + sun * uLight * (patch * 0.5 + glow * 0.03);

  // Dust motes: one per sparse grid cell, drifting up slowly, only in the beam.
  vec2 dp = p + vec2(0.0, -uTime * 0.0045);
  float cell = 0.028;
  vec2 id = floor(dp / cell);
  float r = hash(id);
  // The sell band's still keeps only a few, faint motes, inside the beam (on a still image many
  // bright points read as stars or noise).
  if (r > mix(0.985, 0.86, uBars)) {
    vec2 at = 0.25 + 0.5 * vec2(hash(id + 7.1), hash(id + 3.3));
    at += 0.12 * vec2(sin(uTime * 0.3 + r * 40.0), cos(uTime * 0.23 + r * 17.0));
    float d = length(fract(dp / cell) - at) * cell;
    float mote = smoothstep(uPx * 1.6, 0.0, d) * (0.55 + 0.45 * sin(uTime * 0.7 + r * 60.0));
    float inBeam = mix(light, smoothstep(0.35, -0.15, open) * ahead, uBars);
    col += sun * mote * inBeam * uLight * mix(0.18, 0.5, uBars);
  }

  // Back to sRGB, then film grain (also breaks the banding of the gradients).
  col = pow(max(col, 0.0), vec3(1.0 / 2.2));
  col += (hash(gl_FragCoord.xy + fract(uTime * 7.0) * 113.0) - 0.5) * uGrain;
  gl_FragColor = vec4(col, 1.0);
}`;

const toLinear = (hex) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => (c / 255) ** 2.2);
};

/** Homography of the unit square onto quad [p00, p10, p11, p01], inverted (wall -> square). */
function squareFromQuad([[x0, y0], [x1, y1], [x2, y2], [x3, y3]]) {
  const dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3;
  const dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
  const den = dx1 * dy2 - dx2 * dy1;
  const g = (dx3 * dy2 - dx2 * dy3) / den;
  const h = (dx1 * dy3 - dx3 * dy1) / den;
  const m = [x1 - x0 + g * x1, x3 - x0 + h * x3, x0, y1 - y0 + g * y1, y3 - y0 + h * y3, y0, g, h, 1];
  const [a, b, c, d, e, f, k, l, n] = m;
  const A = e * n - f * l, B = -(d * n - f * k), C = d * l - e * k;
  const det = a * A + b * B + c * C;
  const inv = [A, -(b * n - c * l), b * f - c * e, B, a * n - c * k, -(a * f - c * d), C, -(a * l - b * k), a * e - b * d]
    .map((v) => v / det);
  // Column-major for uniformMatrix3fv.
  return [inv[0], inv[3], inv[6], inv[1], inv[4], inv[7], inv[2], inv[5], inv[8]];
}

/** Sell band: a long beam across the whole screen, from the top left (its soft end, the arch) to
 * the bottom right (its sharp end, the sill, off screen), passing behind the form's panel and
 * above the title; the sun almost grazing. No glazing bars: the arched window stays the hero's. */
function beamQuad(aspect) {
  // Centre line from A to B (fractions of the width, height from the bottom); half width h.
  const [A, B, h] = aspect < 1
    ? [[-0.1, 0.55], [1.1, -0.15], 0.065]    // portrait (cropped to the sides on phones): behind the stacked panel
    : [[-0.05, 1.1], [1.06, 0.12], 0.12];
  const a = [A[0] * aspect, A[1]], b = [B[0] * aspect, B[1]];
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const d = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
  const n = [-d[1], d[0]];                // to the right when going from the sill to the top
  const at = (p, s) => [(p[0] + n[0] * h * s) / aspect, p[1] + n[1] * h * s];
  return [at(b, -1), at(b, 1), at(a, 1), at(a, -1)]; // sill left, sill right, top right, top left
}

/**
 * Where the patch falls (wall units: y 0..1 up, x 0..aspect), never behind the title. Wide
 * screens: the right half, its sill just above the search bar. Tablets: top right, beside the
 * title. Phones: on the right, under the figures, its brightest part behind the search bar.
 * Corners: sill left, sill right, top right, top left, as fractions of the width (x) and height (y).
 * `sun` -1..1 (slow afternoon drift), `scroll` 0..1 (the sun goes down).
 */
function patchQuad(aspect, sun, scroll, layout = "hero") {
  const base = layout === "beam"
    ? beamQuad(aspect)
    : aspect >= 1.2
    ? [[0.60, 0.18], [0.765, 0.125], [0.955, 0.86], [0.745, 0.90]]
    : aspect >= 0.6
      ? [[0.70, 0.42], [0.86, 0.38], [1.02, 0.90], [0.84, 0.93]]
      : [[0.50, 0.02], [0.84, -0.02], [1.06, 0.25], [0.74, 0.28]];
  const drift = 0.018 * sun;            // the patch slides...
  const stretch = 1 + 0.02 * (sun + 1);  // ...and grows longer, 0 to 4 %
  const drop = 0.1 * scroll;             // and goes down as the page scrolls
  const [b0, b1, t1, t0] = base;          // sill left, sill right, top right, top left
  const lift = (top, foot) => [foot[0] + (top[0] - foot[0]) * stretch, foot[1] + (top[1] - foot[1]) * stretch];
  return [b0, b1, lift(t1, b1), lift(t0, b0)].map(([x, y]) => [(x + drift) * aspect, y - drop]);
}

/** Time of the poster's frame: the live light starts from it, so the cross-fade is seamless. */
export const POSTER_TIME = 18;

/**
 * Starts the light on `canvas` (HTMLCanvasElement or OffscreenCanvas). options: { colors: {ink,
 * ink2, brass, amber}, size ({width, height} in CSS pixels; measured if omitted), scale (resolution
 * factor: 0.5 = half the CSS pixels, enlarged by CSS; the light is soft by nature), still
 * (seconds: draw that single frame, no loop), layout ("hero" | "beam"), grain (film grain
 * strength; posters are rendered without it), onLost, onFrame(fps) }.
 * Resolves to { setScroll(0..1), setRunning(bool), resize(size?), dispose() }, or null without WebGL.
 */
export async function createLight(canvas, { colors, size = null, scale = 0.5, still = null, layout = "hero", grain = 0.035, onLost, onFrame } = {}) {
  const attributes = { alpha: false, antialias: false, depth: false, stencil: false, premultipliedAlpha: false, powerPreference: "low-power", preserveDrawingBuffer: still !== null };
  const gl = canvas.getContext("webgl2", attributes) || canvas.getContext("webgl", attributes);
  if (!gl) return null;

  const compile = (type, source) => {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return shader;
  };
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
  gl.bindAttribLocation(program, 0, "aPos");
  gl.linkProgram(program);
  // Compiled off the main thread where the browser allows it: asking for the link status right
  // away would wait for the driver (hundreds of milliseconds on a first visit, cold cache).
  const parallel = gl.getExtension("KHR_parallel_shader_compile");
  while (parallel && !gl.isContextLost() && !gl.getProgramParameter(program, parallel.COMPLETION_STATUS_KHR)) {
    await new Promise((resolve) => setTimeout(resolve, 16));
  }
  if (gl.isContextLost() || !gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn(gl.getProgramInfoLog(program));
    return null;
  }
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const u = {};
  for (const name of ["uRes", "uTime", "uLight", "uWarm", "uGrain", "uBars", "uPx", "uH", "uInk", "uInk2", "uBrass", "uAmber"]) u[name] = gl.getUniformLocation(program, name);
  gl.uniform3fv(u.uInk, toLinear(colors.ink));
  gl.uniform3fv(u.uInk2, toLinear(colors.ink2));
  gl.uniform3fv(u.uBrass, toLinear(colors.brass));
  gl.uniform3fv(u.uAmber, toLinear(colors.amber));

  // Size in CSS pixels: given (an OffscreenCanvas has no layout), or measured.
  let width = 1, height = 1, cssHeight = 1;
  let cssSize = size;
  const resize = () => {
    const rect = cssSize || canvas.getBoundingClientRect();
    cssHeight = Math.max(1, rect.height);
    width = Math.max(1, Math.round(rect.width * scale));
    height = Math.max(1, Math.round(rect.height * scale));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    gl.viewport(0, 0, width, height);
  };

  // The sun's slow afternoon drift, back and forth over 75 s. (The light "rising" at the start
  // is the poster's CSS fade-in: the canvas takes over once it is there.)
  const CYCLE = 75;
  let scroll = 0, running = false, frame = 0, last = 0, lost = false, clock = POSTER_TIME, frames = 0, since = 0;
  const draw = (time) => {
    const sun = Math.sin((time / CYCLE) * Math.PI * 2);
    gl.uniform2f(u.uRes, width, height);
    gl.uniform1f(u.uTime, time);
    // Phones: the patch sits under the figures, so it stays gentler there; the band's beam runs
    // behind its form, so it stays gentler still.
    const strength = layout === "beam" ? 0.6 : width / height < 0.6 ? 0.6 : 1;
    gl.uniform1f(u.uLight, (1 - 0.55 * scroll) * strength);
    gl.uniform1f(u.uWarm, scroll);
    gl.uniform1f(u.uGrain, grain);
    gl.uniform1f(u.uBars, layout === "beam" ? 0 : 1);
    gl.uniform1f(u.uPx, 1 / cssHeight);
    gl.uniformMatrix3fv(u.uH, false, squareFromQuad(patchQuad(width / height, sun, scroll, layout)));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  const loop = (now) => {
    frame = requestAnimationFrame(loop);
    if (now - last < 1000 / 30 - 2) return; // 30 fps is plenty for light this slow
    // The clock only runs while drawing: after a pause the light resumes where it was.
    clock += Math.min(now - last, 100) / 1000;
    last = now;
    draw(clock);
    frames++;
    if (now - since >= 2000) { onFrame?.((frames * 1000) / (now - since)); frames = 0; since = now; }
  };
  const onLostContext = (event) => { event.preventDefault(); lost = true; cancelAnimationFrame(frame); onLost?.(); };
  canvas.addEventListener("webglcontextlost", onLostContext);

  resize();
  draw(still ?? clock);

  return {
    resize: (next) => { if (next) cssSize = next; resize(); if (!running && !lost) draw(still ?? clock); },
    setScroll: (value) => { scroll = Math.min(1, Math.max(0, value)); },
    setRunning: (on) => {
      if (on === running || lost || still !== null) return;
      running = on;
      if (on) { last = since = performance.now(); frames = 0; frame = requestAnimationFrame(loop); } else cancelAnimationFrame(frame);
    },
    dispose: () => {
      cancelAnimationFrame(frame);
      canvas.removeEventListener("webglcontextlost", onLostContext);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
  };
}

/* ---- In a worker: the same light on an OffscreenCanvas -------------------------------------
 * Creating a WebGL context costs 150 to 200 ms on a first visit (the GPU process starts up):
 * done here, the page never waits for it. The module is its own worker script. */
if (typeof document === "undefined" && typeof self !== "undefined") {
  let light = null;
  self.addEventListener("message", async ({ data }) => {
    if (data.type === "init") {
      try {
        light = await createLight(data.canvas, {
          colors: data.colors, size: data.size,
          onLost: () => self.postMessage({ type: "lost" }),
          onFrame: (fps) => self.postMessage({ type: "fps", fps }),
        });
      } catch {
        light = null;
      }
      self.postMessage({ type: light ? "ready" : "lost" });
    } else if (data.type === "size") light?.resize(data.size);
    else if (data.type === "scroll") light?.setScroll(data.value);
    else if (data.type === "run") light?.setRunning(data.on);
  });
}

/** Reads a colour token of the design system (falls back to the given hex). */
const token = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

/** Module workers (`type: "module"`): some browsers have OffscreenCanvas without them. */
function supportsModuleWorkers() {
  let supported = false;
  try {
    // The options are read before the URL is parsed: reading `type` proves it is understood,
    // and the invalid URL then throws, so no worker starts and no request is made.
    new Worker("http://[", { get type() { supported = true; return "module"; } });
  } catch {
    // Expected (invalid URL): only whether `type` was read matters.
  }
  return supported;
}

/** The light in a worker. Resolves to the same small API as createLight, or null. */
function inWorker(canvas, init, { onLost, onFrame }) {
  const offscreen = canvas.transferControlToOffscreen();
  const worker = new Worker(import.meta.url, { type: "module", name: "ymmo-light" });
  const api = {
    resize: (size) => worker.postMessage({ type: "size", size }),
    setScroll: (value) => worker.postMessage({ type: "scroll", value }),
    setRunning: (on) => worker.postMessage({ type: "run", on }),
    dispose: () => worker.terminate(),
  };
  return new Promise((resolve) => {
    worker.addEventListener("message", ({ data }) => {
      if (data.type === "ready") resolve(api);
      else if (data.type === "fps") onFrame(data.fps);
      else if (data.type === "lost") { worker.terminate(); resolve(null); onLost(); }
    });
    worker.addEventListener("error", (event) => { event.preventDefault(); worker.terminate(); resolve(null); onLost(); });
    worker.postMessage({ type: "init", canvas: offscreen, ...init }, [offscreen]);
  });
}

/** Mounts the live light in `hero` (called by app.js). */
export async function mount(hero) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduceMotion.matches) return;
  // The wall is a sibling of the hero (a stage that stays put while the page scrolls), and the
  // threshold of the next section is what one sees through its arched opening: the light runs
  // while either shows.
  const backdrop = hero.parentElement?.querySelector(":scope > .hero-backdrop");
  const arch = document.querySelector(".arch-threshold");
  if (!backdrop) return;

  const canvas = document.createElement("canvas");
  canvas.className = "hero-light";
  canvas.setAttribute("aria-hidden", "true");
  backdrop.querySelector(".hero-poster")?.after(canvas);

  let light = null;
  let done = false;
  let slow = 0;
  let fast; // resolves on the first reading of 20 fps or more
  const fastEnough = new Promise((resolve) => { fast = resolve; });
  let scrollQueued = false;
  let inView = true;
  const size = () => ({ width: canvas.clientWidth, height: canvas.clientHeight });
  const onScroll = () => {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      scrollQueued = false;
      light?.setScroll(Math.min(1, window.scrollY / span));
    });
  };
  const sync = () => light?.setRunning(inView && !document.hidden);
  // The scroll over which the sun goes down: the hero and the threshold (measured on resize only).
  let span = 1;
  const measure = () => { span = Math.max(1, hero.offsetHeight + (arch?.offsetHeight ?? 0)); };
  const resizeObserver = new ResizeObserver(() => { measure(); light?.resize(size()); });
  const showing = new Map();
  const visibility = new IntersectionObserver((entries) => {
    for (const entry of entries) showing.set(entry.target, entry.isIntersecting);
    inView = [...showing.values()].some(Boolean);
    sync();
  });
  const cleanup = () => {
    done = true;
    visibility.disconnect();
    resizeObserver.disconnect();
    window.removeEventListener("scroll", onScroll);
    document.removeEventListener("visibilitychange", sync);
    reduceMotion.removeEventListener?.("change", onMotion);
    light?.dispose();
    light = null;
    // The canvas fades out (its CSS transition) before it goes: the poster comes back softly.
    const shown = backdrop.classList.contains("has-light");
    backdrop.classList.remove("has-light");
    if (shown) setTimeout(() => canvas.remove(), 1300);
    else canvas.remove();
  };
  // Reduced motion switched on while the page is open: back to the still poster.
  const onMotion = (event) => { if (event.matches) cleanup(); };

  const init = {
    colors: {
      ink: token("--ink-900", "#1a1814"),
      ink2: token("--ink-800", "#24211c"),
      brass: token("--brass-300", "#c9ae80"),
      amber: token("--sun-amber", "#d9a05b"),
    },
    size: size(),
  };
  const hooks = {
    onLost: cleanup, // context lost or failure: back to the poster
    // A device that cannot keep 20 fps even for this keeps the poster (two slow readings in a row,
    // 2 s each). The canvas is only shown after a good reading, so it never appears to vanish.
    onFrame: (fps) => {
      slow = fps < 20 ? slow + 1 : 0;
      if (!slow) fast();
      if (slow >= 2) cleanup();
    },
  };
  try {
    light = typeof canvas.transferControlToOffscreen === "function" && supportsModuleWorkers()
      ? await inWorker(canvas, init, hooks)
      : await createLight(canvas, { ...init, ...hooks });
  } catch {
    light = null;
  }
  if (done) { light?.dispose(); return; }
  if (!light) { cleanup(); return; }

  // The canvas fades in over the poster once the poster has finished rising (its CSS intro), so the
  // sun comes out only once, and once the device has shown it keeps up.
  const poster = backdrop.querySelector(".hero-poster img");
  const rising = poster?.getAnimations?.().find((animation) => animation.animationName === "light-rise");
  Promise.all([Promise.resolve(rising?.finished).catch(() => {}), fastEnough]).then(() => {
    if (light) requestAnimationFrame(() => backdrop.classList.add("has-light"));
  });
  window.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("visibilitychange", sync);
  reduceMotion.addEventListener?.("change", onMotion);
  window.addEventListener("pagehide", (event) => { if (!event.persisted) cleanup(); });
  resizeObserver.observe(canvas);
  visibility.observe(hero);
  if (arch) visibility.observe(arch);
  measure();
  onScroll();
  sync();
}
