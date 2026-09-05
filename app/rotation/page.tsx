"use client";

import { useEffect, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import type { RotationRow } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";

type RotationReport = {
  latest_date: string;
  benchmark: string;
  market_regime: string;
  risk_on_score: number;
  strongest: string[];
  weakest: string[];
  rows: RotationRow[];
  warnings: string[];
};

function pct(v: number) {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export default function RotationPage() {
  const [data, setData] = useState<RotationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function load() {
    try {
      setError(null);
      setData(await apiGet<RotationReport>("/api/rotation?include_themes=false"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function refreshData() {
    setRunning(true);
    try {
      await apiPost("/api/rotation/refresh?include_themes=false");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error && !data) {
    return (
      <>
        <PageHeader
          title="Money Rotation"
          subtitle="Sector leadership and relative strength versus SPY."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!data) return <Loading />;

  return (
    <>
      <PageHeader
        title="Money Rotation"
        subtitle="Sector leadership and relative strength versus SPY."
      />

      <div className="toolbar">
        <button className="button primary" onClick={refreshData} disabled={running}>
          {running ? "Refreshing Yahoo Finance…" : "Refresh rotation data"}
        </button>
        <button className="button" onClick={load}>
          Refresh view
        </button>
      </div>

      {error && <ErrorBox message={error} />}

      <section className="metric-grid rotation-summary">
        <div className="metric-card">
          <span className="eyebrow">Regime</span>
          <strong className={`regime ${data.market_regime}`}>
            {data.market_regime}
          </strong>
          <span className="muted">As of {data.latest_date}</span>
        </div>

        <div className="metric-card score-card">
          <ScoreRing score={data.risk_on_score} label="Risk-On" />
        </div>

        <div className="metric-card">
          <span className="eyebrow">Strongest</span>
          <div className="ticker-chip-row">
            {data.strongest.map((ticker) => (
              <span className="ticker-chip" key={ticker}>
                {ticker}
              </span>
            ))}
          </div>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Weakest</span>
          <div className="ticker-chip-row">
            {data.weakest.map((ticker) => (
              <span className="ticker-chip muted-chip" key={ticker}>
                {ticker}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        {data.rows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Sector</th>
                  <th>1D</th>
                  <th>5D</th>
                  <th>20D</th>
                  <th>Rel 5D</th>
                  <th>Rel 20D</th>
                  <th>Score</th>
                  <th>Flow</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.ticker}>
                    <td>#{row.rank}</td>
                    <td>
                      <strong>{row.ticker}</strong>
                      <div className="subcell">{row.name}</div>
                    </td>
                    <td className={row.return_1d >= 0 ? "positive" : "negative"}>
                      {pct(row.return_1d)}
                    </td>
                    <td className={row.return_5d >= 0 ? "positive" : "negative"}>
                      {pct(row.return_5d)}
                    </td>
                    <td className={row.return_20d >= 0 ? "positive" : "negative"}>
                      {pct(row.return_20d)}
                    </td>
                    <td>{pct(row.relative_5d)}</td>
                    <td>{pct(row.relative_20d)}</td>
                    <td>
                      <span className="score-badge">{row.rotation_score}</span>
                    </td>
                    <td>
                      <span className={`flow-pill ${row.flow}`}>
                        {row.flow}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState text="No money-rotation rows are available." />
        )}
      </section>
    </>
  );
}
