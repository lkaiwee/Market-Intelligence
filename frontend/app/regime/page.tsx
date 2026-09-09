"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

type Component = {
  date: string | null; bars: number; close: number | null; sma50: number | null;
  sma200: number | null; realized_volatility20_pct: number | null;
  above_sma50: boolean | null; above_sma200: boolean | null; available: boolean; reason: string | null;
};
type Regime = {
  as_of: string; calculated_at: string; regime: "risk-on" | "risk-off" | "neutral" | "unknown";
  reasons: string[]; spy: Component;
  breadth: { universe_count: number; eligible_count: number; excluded_count: number; coverage_pct: number; above_sma50_pct: number | null; above_sma200_pct: number | null };
  constituents: (Component & { ticker: string; company_name: string })[];
  methodology: Record<string, string>;
};
const fmt = (value: number | null, suffix = "") => value === null ? "—" : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;

export default function RegimePage() {
  const [data, setData] = useState<Regime | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showExcluded, setShowExcluded] = useState(false);
  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try { setData(await apiGet<Regime>("/api/market-regime")); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <div className="regime-page">
    <PageHeader title="Market Regime Detector" subtitle="7.8 · Completed-session trend, realized volatility and breadth from the stored screening universe." />
    <div className="toolbar"><button className="button" disabled={busy} onClick={load}>{busy ? "Calculating…" : "Recalculate from stored prices"}</button><Link className="button" href="/system">Refresh market data</Link></div>
    {error && <ErrorBox message={error} />}
    {!data && busy && <Loading />}
    {data && <>
      <section className={`panel regime-banner ${data.regime}`}>
        <div><span className="eyebrow">Latest completed U.S. session · {data.as_of}</span><h2>{data.regime === "unknown" ? "Insufficient current data" : data.regime.replace("-", " ")}</h2>{data.reasons.map(reason => <p key={reason}>{reason}</p>)}</div>
        <div className="calculated">Calculated {new Date(data.calculated_at).toLocaleString()}<small>Descriptive rules · no predicted return</small></div>
      </section>
      <div className="regime-grid">
        <section className="panel"><div className="panel-heading"><h2>SPY trend</h2><span className="eyebrow">{data.spy.available ? "Current" : "Unavailable"}</span></div><dl><div><dt>Close · {data.spy.date || "no data"}</dt><dd>{fmt(data.spy.close)}</dd></div><div><dt>50-day moving average</dt><dd>{fmt(data.spy.sma50)}</dd></div><div><dt>200-day moving average</dt><dd>{fmt(data.spy.sma200)}</dd></div></dl><p className="muted">{data.spy.reason || `SPY is ${data.spy.above_sma200 ? "above" : "at or below"} its 200-day average. All averages use completed closing prices.`}</p></section>
        <section className="panel"><div className="panel-heading"><h2>Realized volatility</h2><span className="eyebrow">SPY · 20 returns</span></div><strong className="large">{fmt(data.spy.realized_volatility20_pct, "%")}</strong><p className="muted">Annualized from daily logarithmic returns. Below 25% supports risk-on; 35% or higher triggers the volatility risk-off rule when coverage is sufficient.</p><small>Historical price volatility, not implied volatility or VIX.</small></section>
        <section className="panel breadth"><div className="panel-heading"><h2>Market breadth</h2><span className="eyebrow">Equal weight</span></div>{[["Above SMA50", data.breadth.above_sma50_pct], ["Above SMA200", data.breadth.above_sma200_pct]].map(([label, value]) => <div className="breadth-row" key={String(label)}><div><span>{label}</span><strong>{fmt(value as number | null, "%")}</strong></div><div className="track"><div style={{ width: `${Math.max(0, Math.min(100, Number(value ?? 0)))}%` }} /></div></div>)}<p className="muted">{data.breadth.eligible_count} of {data.breadth.universe_count} stocks eligible ({fmt(data.breadth.coverage_pct, "%")} coverage). {data.breadth.excluded_count} excluded for missing, stale or insufficient data.</p><small>This is your configured screening universe, not the full S&amp;P 500.</small></section>
      </div>
      <section className="panel"><div className="panel-heading"><h2>Component evidence</h2><label><input type="checkbox" checked={showExcluded} onChange={event => setShowExcluded(event.target.checked)} /> Show excluded stocks only</label></div><div className="table-wrap"><table><thead><tr><th>Stock</th><th>Price date</th><th>Close</th><th>SMA50</th><th>SMA200</th><th>Coverage status</th></tr></thead><tbody>{data.constituents.filter(row => !showExcluded || !row.available).map(row => <tr key={row.ticker}><td><Link href={`/stocks/?ticker=${encodeURIComponent(row.ticker)}`}>{row.ticker}</Link><small>{row.company_name}</small></td><td>{row.date || "—"}</td><td>{fmt(row.close)}</td><td>{fmt(row.sma50)}<small>{row.above_sma50 === null ? "" : row.above_sma50 ? "Close above" : "Close at or below"}</small></td><td>{fmt(row.sma200)}<small>{row.above_sma200 === null ? "" : row.above_sma200 ? "Close above" : "Close at or below"}</small></td><td className="reason">{row.available ? "Included" : row.reason}<small>{row.bars} bars in the loaded history</small></td></tr>)}</tbody></table>{showExcluded && data.breadth.excluded_count === 0 && <p className="muted">Every stock has sufficient current history.</p>}</div></section>
      <section className="panel"><div className="panel-heading"><h2>Regime rules</h2></div><dl className="rules">{["risk_on", "risk_off", "neutral", "unknown"].map(key => <div key={key}><dt>{key.replace("_", " ")}</dt><dd>{data.methodology[key]}</dd></div>)}</dl><p className="muted">{data.methodology.volatility}</p><p className="muted">{data.methodology.breadth}</p><p className="muted">{data.methodology.price_source}</p><p className="muted">{data.methodology.interpretation}</p><a className="reference" href={data.methodology.reference_url} target="_blank" rel="noreferrer">Fidelity technical indicator reference ↗</a></section>
    </>}
    <style jsx>{`
      .panel { margin-bottom: 18px; }
      .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
      .regime-banner { display: flex; justify-content: space-between; gap: 24px; border-left: 4px solid var(--muted); }
      .regime-banner h2 { font-size: 32px; text-transform: capitalize; margin: 12px 0; }
      .regime-banner p { max-width: 750px; line-height: 1.6; }
      .risk-on { border-left-color: var(--accent); } .risk-off { border-left-color: var(--red); } .neutral { border-left-color: var(--amber); }
      .calculated, .muted, small { color: var(--muted); font-size: 12px; line-height: 1.7; }
      small { display: block; margin-top: 5px; }
      .regime-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
      .regime-grid .panel { margin-bottom: 0; } .regime-grid { margin-bottom: 18px; } .breadth { grid-column: 1 / -1; }
      dl { margin: 0; } dl div { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-bottom: 1px solid var(--border); }
      dt { color: var(--muted); font-size: 13px; } dd { margin: 0; font-weight: 600; }
      .large { font-size: 38px; display: block; margin: 15px 0; }
      .breadth-row { margin-bottom: 16px; } .breadth-row > div:first-child { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
      .track { height: 8px; background: var(--panel-3); border-radius: 5px; overflow: hidden; } .track > div { background: var(--blue); height: 100%; }
      label { display: flex; gap: 8px; align-items: center; color: var(--muted); font-size: 12px; }
      .reason { white-space: normal; min-width: 200px; max-width: 350px; }
      .rules dt { min-width: 100px; text-transform: capitalize; } .rules dd { font-size: 13px; font-weight: 400; line-height: 1.6; }
      .reference { color: var(--accent); }
      @media (max-width: 800px) { .regime-grid { grid-template-columns: 1fr; } .regime-banner { flex-direction: column; } .panel-heading { flex-wrap: wrap; } }
    `}</style>
  </div>;
}
