"use client";

// Sparkline — a tiny canvas line chart accumulated from SSE price points.
// Renders nothing meaningful until ~2 points have arrived; fills in over time.

import { useEffect, useRef } from "react";
import type { PricePoint } from "@/lib/types";

// Canvas cannot parse CSS `var(--x)` references. Resolve a possibly-variable
// color string to a concrete value the 2D context accepts.
function resolveColor(color: string): string {
  const match = color.match(/^var\((--[\w-]+)\)$/);
  if (!match) return color;
  const resolved = getComputedStyle(document.documentElement)
    .getPropertyValue(match[1])
    .trim();
  return resolved || "#56627a";
}

interface SparklineProps {
  data: PricePoint[];
  width?: number;
  height?: number;
  color: string;
}

export function Sparkline({
  data,
  width = 96,
  height = 28,
  color,
}: SparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const drawColor = resolveColor(color);

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (data.length < 2) {
      // Idle baseline so the cell isn't empty before data arrives.
      ctx.strokeStyle = "rgba(86, 98, 122, 0.45)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      return;
    }

    const values = data.map((d) => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 3;
    const usableH = height - pad * 2;

    const x = (i: number) => (i / (data.length - 1)) * width;
    const y = (v: number) => pad + usableH - ((v - min) / range) * usableH;

    // Gradient fill under the line.
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, `${drawColor}38`);
    gradient.addColorStop(1, `${drawColor}00`);

    ctx.beginPath();
    ctx.moveTo(x(0), y(values[0]));
    for (let i = 1; i < data.length; i++) {
      ctx.lineTo(x(i), y(values[i]));
    }
    ctx.lineTo(x(data.length - 1), height);
    ctx.lineTo(x(0), height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // The line itself.
    ctx.beginPath();
    ctx.moveTo(x(0), y(values[0]));
    for (let i = 1; i < data.length; i++) {
      ctx.lineTo(x(i), y(values[i]));
    }
    ctx.strokeStyle = drawColor;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.stroke();

    // End dot.
    ctx.beginPath();
    ctx.arc(x(data.length - 1), y(values[values.length - 1]), 1.8, 0, Math.PI * 2);
    ctx.fillStyle = drawColor;
    ctx.fill();
  }, [data, width, height, color]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height, display: "block" }}
      aria-hidden="true"
    />
  );
}
