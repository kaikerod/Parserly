"use client";

import { useEffect, useRef } from "react";

/** Decorative-only WebGL background derived from the Stitch design system. */
export function TechnicalShader() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const gl = canvas.getContext("webgl", { alpha: false });
    if (!gl) return;
    // Keep a non-null reference for callbacks declared below. TypeScript does
    // not retain control-flow narrowing for the WebGL context inside closures.
    const webgl: WebGLRenderingContext = gl;

    const vertexSource = `attribute vec2 a_position; varying vec2 v_uv; void main() { v_uv = a_position * .5 + .5; gl_Position = vec4(a_position, 0., 1.); }`;
    const fragmentSource = `precision highp float; varying vec2 v_uv; uniform float u_time; uniform vec2 u_resolution; uniform vec2 u_mouse;
      float grid(vec2 uv, float spacing) { vec2 cell = abs(fract(uv / spacing - .5) - .5) / fwidth(uv / spacing); return 1. - min(min(cell.x, cell.y), 1.); }
      void main() { vec2 uv = v_uv; vec2 mouse = u_mouse / u_resolution; vec3 color = vec3(.043, .043, .047); vec3 accent = vec3(.27, 1., .45);
        color += accent * grid(uv, .1) * .05; color += accent * grid(uv, .02) * .018;
        float glow = smoothstep(.32, 0., distance(uv, mouse)); color += accent * glow * .13;
        color += accent * sin(uv.y * 10. + u_time * 2.) * .009 * glow;
        color *= smoothstep(1.45, .5, length(uv - .5)); gl_FragColor = vec4(color, 1.); }`;

    function shader(type: number, source: string) {
      const value = webgl.createShader(type);
      if (!value) return null;
      webgl.shaderSource(value, source);
      webgl.compileShader(value);
      return webgl.getShaderParameter(value, webgl.COMPILE_STATUS) ? value : null;
    }

    const vertex = shader(webgl.VERTEX_SHADER, vertexSource);
    const fragment = shader(webgl.FRAGMENT_SHADER, fragmentSource);
    const program = webgl.createProgram();
    if (!vertex || !fragment || !program) return;
    webgl.attachShader(program, vertex);
    webgl.attachShader(program, fragment);
    webgl.linkProgram(program);
    if (!webgl.getProgramParameter(program, webgl.LINK_STATUS)) return;
    webgl.useProgram(program);

    const buffer = webgl.createBuffer();
    if (!buffer) return;
    webgl.bindBuffer(webgl.ARRAY_BUFFER, buffer);
    webgl.bufferData(webgl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), webgl.STATIC_DRAW);
    const position = webgl.getAttribLocation(program, "a_position");
    webgl.enableVertexAttribArray(position);
    webgl.vertexAttribPointer(position, 2, webgl.FLOAT, false, 0, 0);
    const time = webgl.getUniformLocation(program, "u_time");
    const resolution = webgl.getUniformLocation(program, "u_resolution");
    const mouseUniform = webgl.getUniformLocation(program, "u_mouse");
    let mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    let frame = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(window.innerWidth * dpr));
      canvas.height = Math.max(1, Math.floor(window.innerHeight * dpr));
    };
    const move = (event: PointerEvent) => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      mouse = { x: event.clientX * dpr, y: (window.innerHeight - event.clientY) * dpr };
    };
    const render = (milliseconds: number) => {
      webgl.viewport(0, 0, canvas.width, canvas.height);
      webgl.uniform1f(time, milliseconds / 1000);
      webgl.uniform2f(resolution, canvas.width, canvas.height);
      webgl.uniform2f(mouseUniform, mouse.x, mouse.y);
      webgl.drawArrays(webgl.TRIANGLE_STRIP, 0, 4);
      frame = window.requestAnimationFrame(render);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", move, { passive: true });
    frame = window.requestAnimationFrame(render);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      webgl.deleteBuffer(buffer);
      webgl.deleteProgram(program);
      webgl.deleteShader(vertex);
      webgl.deleteShader(fragment);
    };
  }, []);

  return <canvas ref={canvasRef} className="technical-shader" aria-hidden="true" />;
}
