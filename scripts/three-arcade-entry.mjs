// Entry point of the vendored Three.js bundle used by the home arcade (arcade-scene.js).
// Only the classes the home arcade needs are exported, so the bundle stays small.
// Rebuild: see app/static/vendor/three/README.md
export {
  ACESFilmicToneMapping,
  AdditiveBlending,
  BoxGeometry,
  Color,
  DirectionalLight,
  DoubleSide,
  ExtrudeGeometry,
  FogExp2,
  HemisphereLight,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
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
