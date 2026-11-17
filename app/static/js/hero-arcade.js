/* Ymmo — 3D stone arcade behind the home hero: page-side controller.
 *
 * Purely decorative progressive enhancement, loaded on demand by app.js once the page is idle.
 * The SVG arcade stays in the HTML and is only hidden once the first 3D frame is on screen
 * (class `has-arcade-3d` on .hero): without JS, WebGL, or if anything fails, nothing changes.
 *
 * Rendering happens in a Web Worker on an OffscreenCanvas when the browser supports it, so
 * parsing Three.js, compiling shaders and drawing frames never block the main thread. Older
 * browsers run the same scene (arcade-scene.js) here, split into short tasks.
 * This module only measures the layout, reads the colour tokens and forwards input.
 */

const query = new URL(import.meta.url).search; // ?v=ASSET_VERSION, reused for the sibling modules
const SCENE_URL = new URL(`./arcade-scene.js${query}`, import.meta.url).href;
const WORKER_URL = new URL(`./arcade-worker.js${query}`, import.meta.url).href;
const MAX_DPR = 1.5;

/** Design tokens straight from the stylesheet, so the scene follows the palette. */
function palette() {
  const style = getComputedStyle(document.documentElement);
  const token = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
  return {
    ink: token("--ink-900", "#1a1814"),
    inkSoft: token("--ink-800", "#24211c"),
    stone: token("--ivory-300", "#e4dccd"),
    stoneDark: token("--stone-400", "#d6ccbb"),
    brass: token("--brass-300", "#c9ae80"),
    amber: "#d98a4e",
  };
}

/** Scene in a worker: returns {ready, send, dispose}; `ready` rejects if anything goes wrong. */
function workerBackend(canvas, init) {
  const offscreen = canvas.transferControlToOffscreen();
  const worker = new Worker(WORKER_URL, { type: "module", name: "ymmo-arcade" });
  let onFailure = () => {};
  const ready = new Promise((resolve, reject) => {
    worker.addEventListener("message", ({ data }) => {
      if (data.type === "ready") resolve();
      else if (data.type === "failed") { reject(new Error(data.reason || "arcade failed")); onFailure(); }
    });
    worker.addEventListener("error", (event) => { event.preventDefault(); reject(new Error("worker error")); onFailure(); });
  });
  worker.postMessage({ type: "init", canvas: offscreen, ...init }, [offscreen]);
  return {
    ready,
    send: (message) => worker.postMessage(message),
    dispose: () => worker.terminate(),
    set onFailure(callback) { onFailure = callback; },
  };
}

/** Same scene on the main thread (no OffscreenCanvas): set up in short, yielding steps. */
function mainThreadBackend(canvas, init) {
  let arcade = null;
  let onFailure = () => {};
  const ready = import(SCENE_URL)
    .then(({ createArcade }) => createArcade(canvas, { ...init, onLost: () => onFailure() }))
    .then((created) => {
      if (!created) throw new Error("WebGL unavailable");
      arcade = created;
    });
  return {
    ready,
    send: (message) => arcade?.handle(message),
    dispose: () => arcade?.dispose(),
    set onFailure(callback) { onFailure = callback; },
  };
}

export async function mount(hero) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduceMotion.matches) return;

  const canvas = document.createElement("canvas");
  canvas.className = "hero-arcade";
  canvas.setAttribute("aria-hidden", "true");
  canvas.setAttribute("role", "presentation");
  const fallback = hero.querySelector(".arches");
  if (fallback) fallback.after(canvas);
  else hero.prepend(canvas);

  // ---- Layout: the canvas never sits under the small copy -------------------------------
  // Wide screens: it starts where the text ends. Stacked layouts: a faint veil (CSS mask)
  // behind the figures, full strength just below them, horizon between figures and search.
  const wide = window.matchMedia("(min-width: 64rem)");
  const copy = [...hero.querySelectorAll(".eyebrow, h1, .lead, .hero-stats li")];
  const stats = hero.querySelector(".hero-stats");
  const panel = hero.querySelector(".search-panel");
  const textRight = (el) => {
    const range = document.createRange();
    range.selectNodeContents(el);
    return Math.max(0, ...[...range.getClientRects()].map((rect) => rect.right));
  };
  const measure = () => {
    const box = hero.getBoundingClientRect();
    const narrow = !wide.matches;
    let horizon = null;
    if (!narrow) {
      // The gallery starts a little after the longest line (5 % of the hero width), so the
      // title's last glyph never touches an arch; the CSS mask then fades it in.
      const right = Math.max(...copy.map(textRight)) - box.left + box.width * 0.05;
      hero.style.setProperty("--arcade-left", `${Math.round(Math.max(0, right - 48))}px`);
      hero.style.setProperty("--arcade-top", "0px");
    } else {
      const statsBox = stats.getBoundingClientRect();
      const top = Math.round(Math.max(0, statsBox.top - box.top - 160));
      const solid = Math.round(statsBox.bottom - box.top - top + 6);
      const panelTop = (panel ? panel.getBoundingClientRect().top : box.bottom) - box.top - top;
      hero.style.setProperty("--arcade-left", "0px");
      hero.style.setProperty("--arcade-top", `${top}px`);
      hero.style.setProperty("--arcade-solid", `${solid}px`);
      horizon = (solid + panelTop) / 2 / Math.max(1, box.height - top);
    }
    return { width: canvas.clientWidth, height: canvas.clientHeight, narrow, horizon };
  };

  const init = { colors: palette(), dpr: Math.min(window.devicePixelRatio || 1, MAX_DPR), view: measure() };
  const offscreen = typeof canvas.transferControlToOffscreen === "function" && typeof Worker === "function";
  let backend;
  try {
    backend = offscreen ? workerBackend(canvas, init) : mainThreadBackend(canvas, init);
  } catch {
    backend = null;
  }

  // ---- Input forwarded to the scene ----------------------------------------------------
  const onPointer = (event) => backend.send({
    type: "pointer",
    x: (event.clientX / window.innerWidth) * 2 - 1,
    y: (event.clientY / window.innerHeight) * 2 - 1,
  });
  const onScroll = () => backend.send({
    type: "scroll",
    progress: Math.min(1, Math.max(0, window.scrollY / Math.max(1, hero.offsetHeight))),
  });
  const resizeObserver = new ResizeObserver(() => backend.send({ type: "resize", view: measure() }));

  // The loop only runs while the hero is on screen and the tab is visible.
  let inView = true;
  const syncRunning = () => backend.send({ type: "run", on: inView && !document.hidden });
  const visibility = new IntersectionObserver((entries) => {
    inView = entries.some((entry) => entry.isIntersecting);
    syncRunning();
  });

  const cleanup = () => {
    visibility.disconnect();
    resizeObserver.disconnect();
    window.removeEventListener("pointermove", onPointer);
    window.removeEventListener("scroll", onScroll);
    document.removeEventListener("visibilitychange", syncRunning);
    reduceMotion.removeEventListener?.("change", onMotionChange);
    backend?.dispose();
    hero.classList.remove("has-arcade-3d");
    ["--arcade-left", "--arcade-top", "--arcade-solid"].forEach((name) => hero.style.removeProperty(name));
    canvas.remove();
  };
  // Reduced motion switched on while the page is open: back to the still SVG.
  const onMotionChange = (event) => { if (event.matches) cleanup(); };

  if (!backend) {
    cleanup();
    return;
  }
  backend.onFailure = cleanup;
  try {
    await backend.ready;
  } catch {
    cleanup(); // no WebGL, worker or module error: the SVG arcade stays
    return;
  }

  hero.classList.add("has-arcade-3d");
  if (window.matchMedia("(pointer: fine)").matches) window.addEventListener("pointermove", onPointer, { passive: true });
  window.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("visibilitychange", syncRunning);
  reduceMotion.addEventListener?.("change", onMotionChange);
  window.addEventListener("pagehide", (event) => { if (!event.persisted) cleanup(); }, { once: true });
  resizeObserver.observe(hero);
  visibility.observe(hero);
  onScroll();
  syncRunning();
}
