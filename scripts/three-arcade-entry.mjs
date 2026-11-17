// Entry point of the vendored Three.js bundle used by app/static/js/hero-arcade.js.
// Only the classes the home arcade needs are exported, so the bundle stays small.
// Rebuild: see app/static/vendor/three/README.md
export {
  ACESFilmicToneMapping,
  BoxGeometry,
  Color,
  DirectionalLight,
  ExtrudeGeometry,
  FogExp2,
  HemisphereLight,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  PCFShadowMap,
  PerspectiveCamera,
  PlaneGeometry,
  Scene,
  Shape,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from "three";
