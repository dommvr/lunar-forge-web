"use client";

import { useEffect, useRef } from "react";

import styles from "./EmberField.module.css";

/**
 * Parameters are the spec panel in `project/Landing.dc.html` verbatim.
 * The mockup scaled density by canvas height because the frame was page-tall;
 * the real layer is viewport-fixed, so the per-viewport figures apply directly.
 */
const CONFIG = {
  bandWidth: 0.14, // fraction of viewport width each edge spawns within
  life: [4.5, 9.5], // seconds
  riseSpeed: [8, 22], // px/s upward
  driftInward: [2, 11], // px/s toward centre
  wobbleAmp: [3, 11], // px lateral
  wobbleSpeed: [0.25, 0.6],
  radius: [0.6, 2.2], // px
  brightChance: 0.12,
  palette: ["#E8783A", "#F0925C", "#C9581F", "#8A4A22"],
  brightColor: "#FFD2A1",
} as const;

const DESKTOP = { maxParticles: 44, spawnPerSecond: 7, bandScale: 1, seed: 22 };
const MOBILE = { maxParticles: 18, spawnPerSecond: 4, bandScale: 2.4, seed: 9 };

type Particle = {
  x: number;
  y: number;
  dir: 1 | -1;
  vy: number;
  vx: number;
  amp: number;
  ws: number;
  ph: number;
  r: number;
  life: number;
  age: number;
  col: string;
  bright: boolean;
};

const rnd = (a: number, b: number) => a + Math.random() * (b - a);

export function EmberField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const mobileQuery = window.matchMedia("(max-width: 767px)");
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    let tuning = mobileQuery.matches ? MOBILE : DESKTOP;
    let width = 0;
    let height = 0;
    const particles: Particle[] = [];

    const spawn = (seeded: boolean) => {
      const left = Math.random() < 0.5;
      const band = width * CONFIG.bandWidth * tuning.bandScale;
      const bright = Math.random() < CONFIG.brightChance;
      particles.push({
        x: left ? rnd(-8, band) : rnd(width - band, width + 8),
        y: rnd(0, height + 12),
        dir: left ? 1 : -1,
        vy: rnd(CONFIG.riseSpeed[0], CONFIG.riseSpeed[1]),
        vx: rnd(CONFIG.driftInward[0], CONFIG.driftInward[1]),
        amp: rnd(CONFIG.wobbleAmp[0], CONFIG.wobbleAmp[1]),
        ws: rnd(CONFIG.wobbleSpeed[0], CONFIG.wobbleSpeed[1]),
        ph: Math.random() * Math.PI * 2,
        r: rnd(CONFIG.radius[0], CONFIG.radius[1]) * (bright ? 1.35 : 1),
        life: rnd(CONFIG.life[0], CONFIG.life[1]),
        age: seeded ? rnd(0, 2) : 0,
        col: bright
          ? CONFIG.brightColor
          : CONFIG.palette[(Math.random() * CONFIG.palette.length) | 0],
        bright,
      });
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";
      for (const p of particles) {
        const t = p.age / p.life;
        // Fade in over 0–12% of life, hold to 60%, fade out to 0 by 100%.
        const fade = t < 0.12 ? t / 0.12 : t > 0.6 ? 1 - (t - 0.6) / 0.4 : 1;
        const alpha = Math.max(0, fade) * (p.bright ? 0.95 : 0.62);
        const x = p.x + Math.sin(p.ph + p.age * p.ws) * p.amp;
        const r = p.r * (1 - t * 0.45); // shrinks to 55% over life
        const glowR = Math.max(r * 6, 5);
        const g = ctx.createRadialGradient(x, p.y, 0, x, p.y, glowR);
        g.addColorStop(0, p.col);
        g.addColorStop(0.35, `${p.col}66`);
        g.addColorStop(1, `${p.col}00`);
        ctx.globalAlpha = alpha * 0.5;
        ctx.beginPath();
        ctx.arc(x, p.y, glowR, 0, Math.PI * 2);
        ctx.fillStyle = g;
        ctx.fill();
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.arc(x, p.y, Math.max(r, 0.35), 0, Math.PI * 2);
        ctx.fillStyle = p.col;
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    };

    const reseed = () => {
      particles.length = 0;
      for (let i = 0; i < tuning.seed; i += 1) spawn(true);
      draw();
    };

    resize();
    reseed();

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    /* prefers-reduced-motion: one static seeded field, no rAF loop. */
    if (motionQuery.matches) {
      return () => observer.disconnect();
    }

    let raf = 0;
    let last = performance.now();
    let debt = 0;

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      debt += dt * tuning.spawnPerSecond;
      while (debt >= 1) {
        debt -= 1;
        if (particles.length < tuning.maxParticles) spawn(false);
      }
      for (let i = particles.length - 1; i >= 0; i -= 1) {
        const p = particles[i];
        p.age += dt;
        p.y -= p.vy * dt;
        p.x += p.vx * p.dir * dt;
        if (p.age >= p.life || p.y < -20) particles.splice(i, 1);
      }
      draw();
      raf = requestAnimationFrame(frame);
    };

    const start = () => {
      cancelAnimationFrame(raf);
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };

    /* Pause only while the document is hidden — never on scroll position. */
    const onVisibility = () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else start();
    };

    const onBreakpoint = () => {
      tuning = mobileQuery.matches ? MOBILE : DESKTOP;
      reseed();
    };

    document.addEventListener("visibilitychange", onVisibility);
    mobileQuery.addEventListener("change", onBreakpoint);
    start();

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      mobileQuery.removeEventListener("change", onBreakpoint);
    };
  }, []);

  return (
    <div className={styles.layer} aria-hidden="true">
      <div className={styles.glow} />
      <canvas ref={canvasRef} className={styles.canvas} />
    </div>
  );
}
