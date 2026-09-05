export function ScoreRing({
  score,
  label,
}: {
  score: number | null;
  label: string;
}) {
  const value = score ?? 0;
  const degrees = Math.max(0, Math.min(100, value)) * 3.6;

  return (
    <div className="score-block">
      <div
        className="score-ring"
        style={{
          background: `conic-gradient(var(--accent) ${degrees}deg, var(--panel-3) ${degrees}deg)`,
        }}
      >
        <div className="score-ring-inner">
          <strong>{score ?? "—"}</strong>
          <span>/100</span>
        </div>
      </div>
      <span>{label}</span>
    </div>
  );
}
