# three.js (vendored subset)

- Version: **three 0.187.0** (MIT, see `LICENSE`)
- File: `three.arcade.min.js`, an ES module with only the classes exported by
  `scripts/three-arcade-entry.mjs` (tree-shaken, minified, ~143 KB gzip).
- Used by `app/static/js/hero-arcade.js` (home hero), loaded on demand.

Rebuild (outside the repo, no Node dependency is committed):

```sh
npm install three@0.187.0 esbuild
npx esbuild scripts/three-arcade-entry.mjs --bundle --format=esm --minify --target=es2020 \
  --legal-comments=none \
  "--banner:js=/*! three.js 0.187.0 (subset for the Ymmo home arcade) | MIT License | https://threejs.org/ */" \
  --outfile=app/static/vendor/three/three.arcade.min.js
```

The URL carries `?v={{ ASSET_VERSION }}` like the other assets: the hash covers this file.
