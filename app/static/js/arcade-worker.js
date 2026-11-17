/* Ymmo — Web Worker that renders the home arcade on an OffscreenCanvas.
 * Three.js is parsed, the scene built and every frame drawn here, never on the main thread.
 * Protocol: see createArcade() in arcade-scene.js; the worker answers "ready" once the first
 * frame is drawn, or "failed" (the page then keeps its SVG arcade).
 */
const SCENE_URL = new URL(`./arcade-scene.js${new URL(import.meta.url).search}`, import.meta.url).href;

let arcade = null;
let pending = [];

self.addEventListener("message", async ({ data }) => {
  if (data.type !== "init") {
    if (arcade) arcade.handle(data);
    else pending.push(data); // resize/run sent while the scene is still being built
    return;
  }
  try {
    const { createArcade } = await import(SCENE_URL);
    arcade = await createArcade(data.canvas, {
      colors: data.colors,
      dpr: data.dpr,
      view: data.view,
      onLost: () => self.postMessage({ type: "failed" }),
    });
    if (!arcade) {
      self.postMessage({ type: "failed" });
      return;
    }
    pending.forEach((message) => arcade.handle(message));
    pending = [];
    self.postMessage({ type: "ready" });
  } catch (error) {
    self.postMessage({ type: "failed", reason: String(error) });
  }
});
