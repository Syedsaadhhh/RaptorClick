/* Obsidian Sentinel / hero-only WebGL canvas: organic liquid signal field, never shared with dashboard panels. */

import { MathUtils, Mesh, OrthographicCamera, PlaneGeometry, Scene, ShaderMaterial, Timer, Vector2, WebGLRenderer } from "three";
import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const vertexShader = `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`;

const fragmentShader = `
  precision highp float;

  uniform float uTime;
  uniform vec2 uResolution;
  uniform vec2 uPointer;
  uniform vec2 uPointerVelocity;
  uniform float uPointerInfluence;
  varying vec2 vUv;

  float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
      value += amplitude * noise(p);
      p = p * 2.03 + vec2(17.1, -9.2);
      amplitude *= 0.5;
    }
    return value;
  }

  float blob(vec2 p, vec2 center, vec2 stretch, float warp) {
    vec2 local = (p - center) / stretch;
    float organic = fbm(local * 2.0 + vec2(warp, -warp * 0.7));
    return smoothstep(0.92, 0.08, length(local) - (organic - 0.5) * 0.42);
  }

  void main() {
    vec2 aspect = uResolution / min(uResolution.x, uResolution.y);
    vec2 p = (vUv - 0.5) * aspect;
    float time = uTime * 0.055;

    vec2 drift = vec2(
      fbm(p * 1.35 + vec2(time * 0.72, -time * 0.25)),
      fbm(p * 1.22 + vec2(-time * 0.3, time * 0.62))
    ) - 0.5;

    vec2 cursor = (uPointer - 0.5) * aspect;
    vec2 cursorVelocity = uPointerVelocity * aspect;
    float cursorDistance = length(p - cursor);
    float softWake = exp(-cursorDistance * 1.58) * uPointerInfluence;
    vec2 cursorDirection = normalize(p - cursor + vec2(0.0001));
    vec2 softRepulsion = cursorDirection * softWake * 0.026;
    vec2 softSwirl = vec2(-cursorVelocity.y, cursorVelocity.x) * softWake * 0.52;
    vec2 localFlow = vec2(
      fbm(p * 2.1 + cursorVelocity * 1.8 + vec2(time * 0.35, -time * 0.12)),
      fbm(p * 2.1 - cursorVelocity * 1.4 + vec2(-time * 0.16, time * 0.28))
    ) - 0.5;
    vec2 warped = p + drift * 0.48 + (softRepulsion + softSwirl + localFlow * softWake * 0.024);

    float greenBlob = blob(warped, vec2(-0.30, 0.18), vec2(0.78, 0.64), time * 1.1);
    float limeBlob = blob(warped + drift * 0.2, vec2(0.22, 0.42), vec2(0.52, 0.72), -time * 0.65);
    float cyanBlob = blob(warped - drift * 0.15, vec2(0.48, -0.12), vec2(0.88, 0.52), time * 0.45);
    float bluePocket = blob(warped, vec2(0.20, -0.46), vec2(0.84, 0.48), time * 0.85);

    vec3 charcoal = vec3(0.035, 0.051, 0.086);
    vec3 deepBlue = vec3(0.008, 0.235, 0.455);
    vec3 cyan = vec3(0.008, 0.520, 0.780);
    vec3 electricGreen = vec3(0.133, 0.773, 0.369);
    vec3 acidGreen = vec3(0.518, 0.800, 0.075);

    vec3 color = charcoal;
    color = mix(color, deepBlue, bluePocket * 0.9);
    color = mix(color, cyan, cyanBlob * 0.7);
    color = mix(color, electricGreen, greenBlob * 0.78);
    color = mix(color, acidGreen, limeBlob * 0.58);

    float luminance = dot(color, vec3(0.2126, 0.7152, 0.0722));
    float grain = hash21(gl_FragCoord.xy + vec2(uTime * 13.0, uTime * 7.0));
    float fineNoise = noise(vUv * uResolution.xy * 0.08 + uTime * 1.7);
    color += (grain - 0.5) * 0.065;
    color += (fineNoise - 0.5) * 0.035 * (0.35 + luminance);

    float edgeFade = smoothstep(1.18, 0.26, length((vUv - 0.5) * vec2(1.0, 0.84)));
    color *= mix(0.54, 1.0, edgeFade);
    gl_FragColor = vec4(color, 0.84);
  }
`;

type HeroFluidCanvasProps = {
  hostRef: RefObject<HTMLElement | null>;
};

export default function HeroFluidCanvas({ hostRef }: HeroFluidCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = hostRef.current;
    if (!canvas || !host) return;

    let animationFrame = 0;
    let destroyed = false;
    let pointerTarget = new Vector2(-0.2, -0.2);
    const pointer = new Vector2(-0.2, -0.2);
    const pointerVelocityTarget = new Vector2();
    const pointerVelocity = new Vector2();
    let interactionTarget = 0;
    let interaction = 0;

    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: "high-performance" });
    } catch {
      return;
    }
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x090d16, 0);

    const scene = new Scene();
    const camera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const geometry = new PlaneGeometry(2, 2);
    const material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new Vector2(1, 1) },
        uPointer: { value: pointer.clone() },
        uPointerVelocity: { value: pointerVelocity.clone() },
        uPointerInfluence: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
    });
    scene.add(new Mesh(geometry, material));

    const resize = () => {
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      renderer.setSize(width, height, false);
      material.uniforms.uResolution.value.set(width * renderer.getPixelRatio(), height * renderer.getPixelRatio());
    };

    const onPointerMove = (event: PointerEvent) => {
      if (reduceMotion) return;
      const rect = host.getBoundingClientRect();
      const nextPointer = new Vector2(
        MathUtils.clamp((event.clientX - rect.left) / rect.width, 0, 1),
        MathUtils.clamp(1 - (event.clientY - rect.top) / rect.height, 0, 1),
      );
      pointerVelocityTarget.copy(nextPointer).sub(pointerTarget).multiplyScalar(2.8);
      pointerTarget.copy(nextPointer);
      interactionTarget = 1;
    };
    const onPointerEnter = (event: PointerEvent) => onPointerMove(event);
    const onPointerLeave = () => { interactionTarget = 0; };

    const observer = new ResizeObserver(resize);
    observer.observe(host);
    host.addEventListener("pointermove", onPointerMove, { passive: true });
    host.addEventListener("pointerenter", onPointerEnter, { passive: true });
    host.addEventListener("pointerleave", onPointerLeave, { passive: true });
    resize();

    const timer = new Timer();
    const render = () => {
      if (destroyed) return;
      timer.update();
      const elapsed = reduceMotion ? 0 : timer.getElapsed();
      pointer.lerp(pointerTarget, reduceMotion ? 1 : 0.06);
      pointerVelocityTarget.multiplyScalar(reduceMotion ? 0 : 0.975);
      pointerVelocity.lerp(pointerVelocityTarget, reduceMotion ? 1 : 0.06);
      interactionTarget = Math.max(interactionTarget * (reduceMotion ? 0 : 0.988), pointerVelocityTarget.length() * 0.34);
      interaction = MathUtils.lerp(interaction, interactionTarget, reduceMotion ? 1 : 0.035);
      material.uniforms.uTime.value = elapsed;
      material.uniforms.uPointer.value.copy(pointer);
      material.uniforms.uPointerVelocity.value.copy(pointerVelocity);
      material.uniforms.uPointerInfluence.value = interaction;
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      destroyed = true;
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      host.removeEventListener("pointermove", onPointerMove);
      host.removeEventListener("pointerenter", onPointerEnter);
      host.removeEventListener("pointerleave", onPointerLeave);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, [hostRef]);

  return <canvas ref={canvasRef} className="hero-fluid-canvas" aria-hidden="true" />;
}
