"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ErrorBox } from "@/components/ErrorBox";
import { PageHeader } from "@/components/PageHeader";
import { apiPost } from "@/lib/api";

type Correlation = { left: string; right: string; correlation: number | null; samples: number };
type Metrics = { samples: number; start_date: string; end_date: string; daily_volatility_pct: number; annualized_volatility_pct: number; confidence: number; one_day_var_pct: number; one_day_var_amount: number; one_day_expected_shortfall_pct: number; one_day_expected_shortfall_amount: number; tail_observations: number; worst_day: string; worst_day_return_pct: number; worst_day_pnl: number };
type ScenarioHolding = { ticker: string; market_value: number | null; latest_date: string | null; beta_to_spy: number | null; beta_samples: number; raw_shock_pct: number | null; applied_shock_pct: number | null; source: string; pnl: number | null; stressed_value: number | null };
type Stress = { as_of: string; lookback_sessions: number; position_count: number; priced_market_value: number; covered_market_value: number; covered_priced_value_pct: number | null; included_tickers: string[]; excluded_tickers: string[]; unpriced_tickers: string[]; risk_capital: number; cash: number | null; common_samples: number; metrics: Metrics | null; correlation_tickers: string[]; correlations: Correlation[]; scenario: { mode: string; market_shock_pct: number; holdings: ScenarioHolding[]; covered_pnl: number; total_pnl: number | null; total_return_pct: number | null; missing_tickers: string[] }; warnings: string[]; methodology: string };
const money = (n: number | null) => n === null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const pct = (n: number | null) => n === null ? "—" : `${n.toFixed(2)}%`;

export default function StressPage() {
  const [data, setData] = useState<Stress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("uniform");
  const [shock, setShock] = useState("-10");
  const [lookback, setLookback] = useState("252");
  const [confidence, setConfidence] = useState("0.95");
  const [cash, setCash] = useState("");
  const [shocks, setShocks] = useState<Record<string, string>>({});
  useEffect(() => { let active = true; apiPost<Stress>("/api/stress/analyze", {}).then(r => { if (active) setData(r); }).catch(e => { if (active) setError(String(e.message || e)); }); return () => { active = false; }; }, []);
  async function analyze(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { setData(await apiPost<Stress>("/api/stress/analyze", { mode, market_shock_pct: Number(shock), lookback: Number(lookback), confidence: Number(confidence), cash: cash.trim() ? Number(cash) : null, shocks: Object.fromEntries(Object.entries(shocks).filter(([, value]) => value.trim()).map(([ticker, value]) => [ticker, Number(value)])) })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const correlationMap = new Map(data?.correlations.map(c => [`${c.left}:${c.right}`, c]) || []);
  return <>
    <PageHeader title="Portfolio Stress & Correlation" subtitle="Explore current holdings under historical return patterns and explicit hypothetical shocks." />
    <p className="muted">For USD-quoted holdings and USD cash inputs. No currency conversion is performed.</p>
    {error && <ErrorBox message={error} />}
    <section className="panel"><h2>Scenario assumptions</h2><p className="muted">These calculations use your <Link className="ticker-link" href="/portfolio/">recorded holdings</Link>. Scenarios change analysis only; they do not place trades or update holdings.</p>
      <form onSubmit={analyze}><div className="research-form">
        <label>Shock model<select value={mode} onChange={e => setMode(e.target.value)}><option value="uniform">Same percentage for every holding</option><option value="beta">SPY market shock × historical beta</option></select></label>
        <label>{mode === "beta" ? "SPY market shock (%)" : "Holding shock (%)"}<input type="number" min="-100" max="300" step="any" value={shock} onChange={e => setShock(e.target.value)} required /></label>
        <label>History window<select value={lookback} onChange={e => setLookback(e.target.value)}><option value="126">126 sessions</option><option value="252">252 sessions</option><option value="504">504 sessions</option></select></label>
        <label>VaR / ES confidence<select value={confidence} onChange={e => setConfidence(e.target.value)}><option value="0.90">90%</option><option value="0.95">95%</option><option value="0.99">99%</option></select></label>
        <label>Cash to include (USD, optional)<input type="number" min="0" step="any" value={cash} onChange={e => setCash(e.target.value)} placeholder="Blank = holdings risk only" /></label>
      </div>
      {!!data?.scenario.holdings.length && <><h3>Individual shock overrides</h3><p className="muted">An entered holding shock replaces the selected model for that holding.</p><div className="research-form">{data.scenario.holdings.map(h => <label key={h.ticker}>{h.ticker} shock (%)<input type="number" min="-100" max="300" step="any" value={shocks[h.ticker] || ""} onChange={e => setShocks(s => ({ ...s, [h.ticker]: e.target.value }))} placeholder="Use selected model" /></label>)}</div></>}
      <button className="button primary" disabled={busy}>{busy ? "Analyzing…" : "Run stress analysis"}</button></form>
    </section>
    {!data && !error && <p className="muted">Loading holdings and historical prices…</p>}
    {data && <>
      {data.position_count === 0 && <section className="panel"><p>No holdings are recorded yet. Add your actual positions in the Portfolio Tracker to run portfolio scenarios.</p></section>}
      {!!data.warnings.length && <section className="panel">{data.warnings.map(w => <p className="muted" key={w}>{w}</p>)}</section>}
      <section className="metric-grid">
        <div className="metric-card"><span className="eyebrow">Covered value</span><strong>{money(data.covered_market_value)}</strong><span className="muted">{pct(data.covered_priced_value_pct)} of priced holdings · {data.included_tickers.length}/{data.position_count} holdings</span></div>
        <div className="metric-card"><span className="eyebrow">Annualized volatility</span><strong>{pct(data.metrics?.annualized_volatility_pct ?? null)}</strong><span className="muted">{data.common_samples} aligned daily observations</span></div>
        <div className="metric-card"><span className="eyebrow">One-day historical VaR</span><strong>{money(data.metrics?.one_day_var_amount ?? null)}</strong><span className="muted">{pct(data.metrics?.one_day_var_pct ?? null)} · {data.metrics ? `${data.metrics.confidence * 100}% confidence` : "Insufficient history"}</span></div>
        <div className="metric-card"><span className="eyebrow">One-day expected shortfall</span><strong>{money(data.metrics?.one_day_expected_shortfall_amount ?? null)}</strong><span className="muted">Average loss in {data.metrics?.tail_observations ?? 0} tail observations</span></div>
      </section>
      <section className="panel"><h2>Historical risk coverage</h2><p className="muted">Completed session: {data.as_of}. Requested window: {data.lookback_sessions} sessions. Included: {data.included_tickers.join(", ") || "none"}. Excluded: {data.excluded_tickers.join(", ") || "none"}. Unpriced: {data.unpriced_tickers.join(", ") || "none"}.</p><p className="muted">Risk capital: {money(data.risk_capital)} {data.cash === null ? "(covered holdings only; no account cash assumed)" : `(including ${money(data.cash)} entered cash)`}. Metrics describe this covered subset, not any excluded holdings.</p>
        {data.metrics && <p>Sample: {data.metrics.start_date} to {data.metrics.end_date}. Worst replayed day: {data.metrics.worst_day}, {pct(data.metrics.worst_day_return_pct)} / {money(data.metrics.worst_day_pnl)} for today&apos;s weights.</p>}
      </section>
      <section className="panel"><h2>Scenario results</h2><p className="muted">Last calculation: {data.scenario.mode === "beta" ? "SPY beta model" : "uniform holding model"}, {pct(data.scenario.market_shock_pct)} base shock, plus entered overrides.</p><div className="metric-grid">
        <div className="metric-card"><span className="eyebrow">Total scenario P&L</span><strong className={(data.scenario.total_pnl ?? 0) < 0 ? "negative" : "positive"}>{money(data.scenario.total_pnl)}</strong><span className="muted">{pct(data.scenario.total_return_pct)} · full total requires all holdings</span></div>
        <div className="metric-card"><span className="eyebrow">Covered scenario P&L</span><strong>{money(data.scenario.covered_pnl)}</strong><span className="muted">Missing: {data.scenario.missing_tickers.join(", ") || "none"}</span></div>
      </div><div className="table-wrap"><table><thead><tr><th>Holding</th><th>Market value</th><th>SPY beta</th><th>Applied shock</th><th>P&L</th><th>Stressed value</th></tr></thead><tbody>{data.scenario.holdings.map(h => <tr key={h.ticker}><td><strong>{h.ticker}</strong><div className="subcell">{h.latest_date || "No price"}</div></td><td>{money(h.market_value)}</td><td>{h.beta_to_spy?.toFixed(2) ?? "—"}<div className="subcell">{h.beta_samples} paired returns</div></td><td>{pct(h.applied_shock_pct)}<div className="subcell">{h.source}{h.raw_shock_pct !== h.applied_shock_pct ? " · price floored at zero" : ""}</div></td><td className={(h.pnl ?? 0) < 0 ? "negative" : "positive"}>{money(h.pnl)}</td><td>{money(h.stressed_value)}</td></tr>)}</tbody></table></div></section>
      {!!data.correlation_tickers.length && <section className="panel"><h2>Daily return correlation</h2><p className="muted">Pearson correlation from pairwise common dates; minimum 60 observations. Values near +1 move together, near −1 move in opposite directions. Hover or focus a cell for sample count. Constant or insufficient series show —.</p><div className="table-wrap"><table><thead><tr><th>Holding</th>{data.correlation_tickers.map(t => <th key={t}>{t}</th>)}</tr></thead><tbody>{data.correlation_tickers.map(left => <tr key={left}><th>{left}</th>{data.correlation_tickers.map(right => { const c = correlationMap.get(`${left}:${right}`); const value = c?.correlation ?? null; return <td key={right} tabIndex={0} title={`${left} / ${right}: ${c?.samples ?? 0} paired observations`} style={value === null ? undefined : { backgroundColor: value >= 0 ? `rgba(41, 211, 154, ${Math.abs(value) * 0.28})` : `rgba(255, 107, 122, ${Math.abs(value) * 0.28})` }}>{value === null ? "—" : value.toFixed(2)}</td>; })}</tr>)}</tbody></table></div></section>}
      <section className="panel"><h2>Method & limitations</h2><p className="muted">{data.methodology}</p><a className="ticker-link" href="https://www.msci.com/research-and-insights/blog-post/backtesting-expected-shortfall" target="_blank" rel="noreferrer">Expected shortfall background · MSCI</a></section>
    </>}
  </>;
}
