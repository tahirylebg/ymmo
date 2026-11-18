// Renders the still images of the home page from the real light shader, and encodes them.
//
//   app/static/img/hero/light-1920.{avif,webp}  hero poster, wide screens (16:9)
//   app/static/img/hero/light-1200.{avif,webp}  hero poster, tablets held upright
//   app/static/img/hero/light-960.{avif,webp}   hero poster, phones (tall framing)
//   app/static/img/hero/beam-1920.{avif,webp}   "Vendre" band: a long beam across the screen
//   app/static/img/hero/beam-900.{avif,webp}    the same, portrait (phones)
//
// Each one is a frame of hero-light.js (same shader, same layout per format, same moment of the
// sun's drift as the live light starts from), so the cross-fade to the live canvas is seamless.
// Rendered without the film grain (it would only weigh on the files: the page adds its own).
// Budget: 40 KB per file. Nothing here is committed as a Node dependency:
//
//   npm install --prefix /tmp/ymmo-render puppeteer-core sharp
//   node scripts/render_hero_poster.mjs --modules /tmp/ymmo-render/node_modules \
//        [--base http://localhost:8000] [--chrome "C:/Program Files/Google/Chrome/Application/chrome.exe"]
//
// The app must be running at --base (it serves /static).
import { createRequire } from "node:module";
import { mkdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, arg, i, all) => (
  arg.startsWith("--") ? [...pairs, [arg.slice(2), all[i + 1]]] : pairs), []));
const modules = args.modules || process.env.YMMO_RENDER_MODULES;
if (!modules) throw new Error("--modules <node_modules with puppeteer-core and sharp> is required");
const require = createRequire(path.join(path.resolve(modules), "noop.js"));
const puppeteer = require("puppeteer-core");
const sharp = require("sharp");
const BASE = args.base || "http://localhost:8000";
const CHROME = args.chrome || process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "app", "static", "img", "hero");
const BUDGET = 40 * 1024;

// The colours are read from the site's own tokens (main.css), like the live light does.
const PAGE = (layout) => `<!doctype html>
<link rel="stylesheet" href="/static/css/main.css?v=render">
<style>html,body{margin:0;background:#1a1814}canvas{display:block;width:100vw;height:100vh}</style>
<canvas></canvas><script type="module">
import { createLight, POSTER_TIME } from "/static/js/hero-light.js?v=render";
const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const light = await createLight(document.querySelector("canvas"), {
  colors: { ink: token("--ink-900"), ink2: token("--ink-800"), brass: token("--brass-300"), amber: token("--sun-amber") },
  scale: 1, still: POSTER_TIME, layout: "${layout}", grain: 0,
});
// No WebGL (or a shader that fails): never encode a blank wall over the committed posters.
window.__done = light ? true : "no-webgl";
</script>`;

async function shoot(browser, html, width, height) {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => console.error("page error:", error.message));
  await page.setRequestInterception(true);
  page.on("request", (request) => (new URL(request.url()).pathname === "/__render.html"
    ? request.respond({ contentType: "text/html", body: html })
    : request.continue()));
  await page.goto(`${BASE}/__render.html`, { waitUntil: "load" });
  await page.waitForFunction("window.__done", { timeout: 60000 });
  if (await page.evaluate(() => window.__done) !== true) throw new Error("WebGL unavailable: posters left untouched");
  const png = await page.screenshot({ type: "png" });
  await page.close();
  return png;
}

/** Highest quality (from `start` down) whose file fits in the budget. */
async function encode(png, name, start = { avif: 80, webp: 90 }) {
  for (const [format, options] of [["avif", { effort: 6, chromaSubsampling: "4:2:0" }], ["webp", { effort: 6, smartSubsample: true }]]) {
    let quality = start[format];
    let buffer;
    for (;;) {
      buffer = await sharp(png)[format]({ quality, ...options }).toBuffer();
      if (buffer.length <= BUDGET || quality <= 20) break;
      quality -= 4;
    }
    const file = path.join(OUT, `${name}.${format}`);
    writeFileSync(file, buffer);
    console.log(`${name}.${format}  q${quality}  ${(statSync(file).size / 1024).toFixed(1)} KB`);
  }
}

mkdirSync(OUT, { recursive: true });
const browser = await puppeteer.launch({ headless: "new", executablePath: CHROME, args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"] });
try {
  // Each poster is rendered at the shape of the hero it covers, so the patch falls where the
  // live light puts it (see patchQuad in hero-light.js).
  await encode(await shoot(browser, PAGE("hero"), 1920, 1080), "light-1920");
  await encode(await shoot(browser, PAGE("hero"), 1200, 1440), "light-1200");
  await encode(await shoot(browser, PAGE("hero"), 960, 2400), "light-960");
  await encode(await shoot(browser, PAGE("beam"), 1920, 1080), "beam-1920");
  await encode(await shoot(browser, PAGE("beam"), 900, 1600), "beam-900");
} finally {
  await browser.close();
}
