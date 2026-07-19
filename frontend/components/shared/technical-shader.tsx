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

    const vertexSource = `attribute vec2 a_position; varying vec2 v_uv; void main() { v_uv = a_position * .5 + .5; gl_Position = vec4(a_position, 0., 1.); }`;
    const fragmentSource = `precision highp float; varying vec2 v_uv; uniform float u_time; uniform vec2 u_resolution; uniform vec2 u_mouse;
      float grid(vec2 uv, float spacing) { vec2 cell = abs(fract(uv / spacing - .5) - .5) / fwidth(uv / spacing); return 1. - min(min(cell.x, cell.y), 1.); }
      void main() { vec2 uv = v_uv; vec2 mouse = u_mouse / u_resolution; vec3 color = vec3(.043, .043, .047); vec3 accent = vec3(.27, 1., .45);
        color += accent * grid(uv, .1) * .05; color += accent * grid(uv, .02) * .018;
        float glow = smoothstep(.32, 0., distance(uv, mouse)); color += accent * glow * .13;
        color += accent * sin(uv.y * 10. + u_time * 2.) * .009 * glow;
        color *= smoothstep(1.45, .5, length(uv - .5)); gl_FragColor = vec4(color, 1.); }`;

    function shader(type: number, source: string) {
      const value = gl.createShader(type);
      if (!value) return null;
      gl.shaderSource(value, source);
      gl.compileShader(value);
      return gl.getShaderParameter(value, gl.COMPILE_STATUS) ? value : null;
    }

    const vertex = shader(gl.VERTEX_SHADER, vertexSource);
    const fragment = shader(gl.FRAGMENT_SHADER, fragmentSource);
    const program = gl.createProgram();
    if (!vertex || !fragment || !program) return;
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    if (!buffer) return;
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const time = gl.getUniformLocation(program, "u_time");
    const resolution = gl.getUniformLocation(program, "u_resolution");
    const mouseUniform = gl.getUniformLocation(program, "u_mouse");
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
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform1f(time, milliseconds / 1000);
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform2f(mouseUniform, mouse.x, mouse.y);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
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
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
    };
  }, []);

  return <canvas ref={canvasRef} className="technical-shader" aria-hidden="true" />;
}
