"use client";

type Point = { date: string; equity: number; benchmark: number };

export function ResearchChart({ points }: { points: Point[] }) {
  if (points.length < 2) return null;
  const values = points.flatMap(point => [point.equity, point.benchmark]);
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const path = (key: "equity" | "benchmark") => points.map((point, index) =>
    `${index ? "L" : "M"}${50 + index / (points.length - 1) * 820},${210 - (point[key] - min) / span * 180}`
  ).join(" ");
  return <figure style={{ margin: 0 }}>
    <svg viewBox="0 0 900 250" role="img" aria-label="Strategy equity in green and buy-and-hold benchmark in blue over the selected simulation dates" style={{ width: "100%", maxHeight: 330 }}>
      <line x1="50" y1="210" x2="870" y2="210" stroke="var(--border)" />
      <text x="50" y="18" fill="var(--muted)" fontSize="12">${max.toLocaleString(undefined, { maximumFractionDigits: 0 })}</text>
      <text x="50" y="228" fill="var(--muted)" fontSize="12">${min.toLocaleString(undefined, { maximumFractionDigits: 0 })}</text>
      <path d={path("benchmark")} fill="none" stroke="var(--blue)" strokeWidth="2" />
      <path d={path("equity")} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <text x="50" y="247" fill="var(--muted)" fontSize="12">{points[0].date}</text>
      <text x="870" y="247" textAnchor="end" fill="var(--muted)" fontSize="12">{points[points.length - 1].date}</text>
    </svg>
    <figcaption className="muted">Green: strategy · Blue: buy and hold · Includes entry costs and open positions marked to close.</figcaption>
  </figure>;
}
