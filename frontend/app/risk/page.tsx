"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ErrorBox } from "@/components/ErrorBox";
import { PageHeader } from "@/components/PageHeader";
import { apiPost } from "@/lib/api";

type Holding = { ticker: string; sector: string; shares: number; current_price: number | null; latest_date: string | null; market_value: number | null; weight_pct: number | null; account_weight_pct: number | null; stop_price: number | null; stop_source: string | null; stop_reached: boolean; planned_downside: number | null; account_risk_pct: number | null };
type Risk = { as_of: string; holdings: Holding[]; sectors: { sector: string; market_value: number; weight_pct: number }[]; position_count: number; total_cost_basis: number; priced_market_value: number; cash: number | null; account_equity: number | null; equity_source: string | null; largest_position_pct: number | null; top_three_pct: number | null; covered_planned_downside: number; risk_coverage_count: number; total_planned_downside: number | null; account_risk_pct: number | null; warnings: string[]; methodology: string };
type Size = { quantity: number; side: string; entry: number; stop: number; risk_per_share: number; risk_budget: number; planned_loss_including_fees: number; notional: number; allocation_pct: number; account_risk_pct: number; limiting_constraints: string[]; cash_limit_applied: boolean; notes: string[] };
const money = (n: number | null) => n === null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const pct = (n: number | null) => n === null ? "—" : `${n.toFixed(2)}%`;
const optional = (s: string) => s.trim() ? Number(s) : null;

export default function RiskPage() {
  const [data, setData] = useState<Risk | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cash, setCash] = useState("");
  const [equity, setEquity] = useState("");
  const [useAtr, setUseAtr] = useState(true);
  const [atrMultiple, setAtrMultiple] = useState("2");
  const [stops, setStops] = useState<Record<string, string>>({});
  const [sizing, setSizing] = useState({ side: "long", entry: "", stop: "", account_equity: "", risk_pct: "1", max_allocation_pct: "10", available_cash: "", fee_budget: "0" });
  const [fractional, setFractional] = useState(false);
  const [sizeResult, setSizeResult] = useState<Size | null>(null);
  const [sizingBusy, setSizingBusy] = useState(false);
  useEffect(() => { let active = true; apiPost<Risk>("/api/risk/analyze", {}).then(r => { if (active) setData(r); }).catch(e => { if (active) setError(String(e.message || e)); }); return () => { active = false; }; }, []);

  async function analyze(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const enteredStops = Object.fromEntries(Object.entries(stops).filter(([, value]) => value.trim()).map(([ticker, value]) => [ticker, Number(value)]));
      setData(await apiPost<Risk>("/api/risk/analyze", { cash: optional(cash), account_equity: optional(equity), stops: enteredStops, use_atr: useAtr, atr_multiplier: Number(atrMultiple) }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function calculateSize(event: FormEvent) {
    event.preventDefault(); setSizingBusy(true); setError(null); setSizeResult(null);
    try { setSizeResult(await apiPost<Size>("/api/risk/size", { side: sizing.side, entry: Number(sizing.entry), stop: Number(sizing.stop), account_equity: Number(sizing.account_equity), risk_pct: Number(sizing.risk_pct), max_allocation_pct: Number(sizing.max_allocation_pct), available_cash: optional(sizing.available_cash), fee_budget: Number(sizing.fee_budget), fractional })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setSizingBusy(false); }
  }
  function sizeField(key: keyof typeof sizing, value: string) { setSizing(s => ({ ...s, [key]: value })); setSizeResult(null); }

  return <>
    <PageHeader title="Portfolio Risk Manager" subtitle="Measure concentration, plan downside and size a position using your own account limits." />
    <p className="muted">For USD-quoted holdings and USD account inputs. No currency conversion is performed.</p>
    {error && <ErrorBox message={error} />}
    <section className="panel"><h2>Account & stop assumptions</h2><p className="muted">Optional account inputs apply only to this calculation. Blank cash does not mean zero account cash. Portfolio holdings remain managed in the <Link className="ticker-link" href="/portfolio/">Portfolio Tracker</Link>.</p>
      <form onSubmit={analyze}>
        <div className="research-form">
          <label>Cash balance (USD, optional)<input type="number" min="0" step="any" value={cash} onChange={e => setCash(e.target.value)} placeholder="Enter your cash balance" /></label>
          <label>Account equity (USD, optional)<input type="number" min="0.01" step="any" value={equity} onChange={e => setEquity(e.target.value)} placeholder="Overrides holdings + entered cash" /></label>
          <label>ATR estimate multiplier<input type="number" min="0.1" max="10" step="0.1" value={atrMultiple} onChange={e => setAtrMultiple(e.target.value)} required /></label>
          <label>Missing-stop treatment<select value={useAtr ? "atr" : "none"} onChange={e => setUseAtr(e.target.value === "atr")}><option value="atr">Use labelled ATR estimates</option><option value="none">Leave risk unavailable</option></select></label>
        </div>
        {!!data?.holdings.length && <div className="research-form">{data.holdings.map(h => <label key={h.ticker}>{h.ticker} stop (optional)<input type="number" min="0.000001" step="any" value={stops[h.ticker] || ""} onChange={e => setStops(s => ({ ...s, [h.ticker]: e.target.value }))} placeholder="Enter your stop" /></label>)}</div>}
        <button className="button primary" disabled={busy}>{busy ? "Calculating…" : "Analyze portfolio risk"}</button>
      </form>
    </section>
    {!data && !error && <p className="muted">Loading portfolio exposure…</p>}
    {data && <>
      <section className="metric-grid">
        <div className="metric-card"><span className="eyebrow">Invested cost</span><strong>{money(data.total_cost_basis)}</strong><span className="muted">{data.position_count} holdings</span></div>
        <div className="metric-card"><span className="eyebrow">Priced market value</span><strong>{money(data.priced_market_value)}</strong><span className="muted">Completed session {data.as_of}</span></div>
        <div className="metric-card"><span className="eyebrow">Account equity</span><strong>{money(data.account_equity)}</strong><span className="muted">{data.equity_source || "No balance assumed"}</span></div>
        <div className="metric-card"><span className="eyebrow">Planned downside</span><strong>{money(data.total_planned_downside)}</strong><span className="muted">{pct(data.account_risk_pct)} of account · {data.risk_coverage_count}/{data.position_count} covered</span></div>
      </section>
      {!!data.warnings.length && <section className="panel">{data.warnings.map(w => <p className="muted" key={w}>{w}</p>)}</section>}
      <section className="panel"><h2>Position concentration & planned risk</h2><p className="muted">Largest position: {pct(data.largest_position_pct)} · Top three: {pct(data.top_three_pct)} of priced holdings. Covered downside subtotal: {money(data.covered_planned_downside)}.</p>
        {!data.holdings.length ? <p>No holdings yet. Add your actual holdings in the Portfolio Tracker to see exposure.</p> : <div className="table-wrap"><table><thead><tr><th>Holding</th><th>Value</th><th>Holding weight</th><th>Account weight</th><th>Stop / source</th><th>Downside</th><th>Account risk</th></tr></thead><tbody>{data.holdings.map(h => <tr key={h.ticker}><td><Link className="ticker-link" href={`/stocks/?ticker=${h.ticker}`}>{h.ticker}</Link><div className="subcell">{h.sector} · {h.latest_date || "No price"}</div></td><td>{money(h.market_value)}</td><td>{pct(h.weight_pct)}</td><td>{pct(h.account_weight_pct)}</td><td>{money(h.stop_price)}{h.stop_reached && <span className="negative"> · reached</span>}<div className="subcell">{h.stop_source || "No stop"}</div></td><td>{money(h.planned_downside)}</td><td>{pct(h.account_risk_pct)}</td></tr>)}</tbody></table></div>}
      </section>
      {!!data.sectors.length && <section className="panel"><h2>Sector exposure</h2><div className="table-wrap"><table><thead><tr><th>Sector</th><th>Market value</th><th>Weight of priced holdings</th></tr></thead><tbody>{data.sectors.map(s => <tr key={s.sector}><td>{s.sector}</td><td>{money(s.market_value)}</td><td><progress value={s.weight_pct} max={100} aria-label={`${s.sector} weight`} /> {pct(s.weight_pct)}</td></tr>)}</tbody></table></div></section>}
    </>}
    <section className="panel"><h2>Position sizing calculator</h2><p className="muted">Planning only. Enter your equity and risk limits; the 1% risk and 10% allocation fields are editable calculation settings, not a recommendation. For shorts, available capital is a conservative notional cap rather than broker margin.</p>
      <form onSubmit={calculateSize}>
        <div className="research-form">
          <label>Direction<select value={sizing.side} onChange={e => sizeField("side", e.target.value)}><option value="long">Long</option><option value="short">Short</option></select></label>
          {([ ["entry", "Entry price (USD)"], ["stop", "Stop price (USD)"], ["account_equity", "Account equity (USD)"], ["risk_pct", "Risk budget (%)"], ["max_allocation_pct", "Maximum allocation (%)"], ["available_cash", "Available cash/capital (optional)"], ["fee_budget", "Total round-trip fees (USD)"] ] as const).map(([key, label]) => <label key={key}>{label}<input type="number" min={key === "available_cash" || key === "fee_budget" ? "0" : "0.000001"} max={key.endsWith("pct") ? "100" : undefined} step="any" required={key !== "available_cash"} value={sizing[key]} onChange={e => sizeField(key, e.target.value)} /></label>)}
          <label>Share precision<select value={fractional ? "fractional" : "whole"} onChange={e => { setFractional(e.target.value === "fractional"); setSizeResult(null); }}><option value="whole">Whole shares</option><option value="fractional">Fractional (6 decimals)</option></select></label>
        </div><button className="button primary" disabled={sizingBusy}>{sizingBusy ? "Calculating…" : "Calculate position size"}</button>
      </form>
      {sizeResult && <div aria-live="polite"><div className="metric-grid" style={{ marginTop: 20 }}>
        <div className="metric-card"><span className="eyebrow">{sizeResult.side} quantity</span><strong>{sizeResult.quantity.toLocaleString("en-US", { maximumFractionDigits: 6 })}</strong><span className="muted">shares at {money(sizeResult.entry)}</span></div>
        <div className="metric-card"><span className="eyebrow">Notional</span><strong>{money(sizeResult.notional)}</strong><span className="muted">{pct(sizeResult.allocation_pct)} of equity</span></div>
        <div className="metric-card"><span className="eyebrow">Planned loss + fees</span><strong>{money(sizeResult.planned_loss_including_fees)}</strong><span className="muted">{pct(sizeResult.account_risk_pct)} of equity · stop {money(sizeResult.stop)}</span></div>
        <div className="metric-card"><span className="eyebrow">Risk budget</span><strong>{money(sizeResult.risk_budget)}</strong><span className="muted">Limited by {sizeResult.limiting_constraints.join(", ")}</span></div>
      </div>{sizeResult.quantity === 0 && <p className="negative">Your limits do not allow the minimum share increment at these prices and fees.</p>}<p className="muted">{sizeResult.cash_limit_applied ? "Entered cash/capital cap applied." : "No cash constraint entered; funding availability has not been checked."}</p>{sizeResult.notes.map(n => <p className="muted" key={n}>{n}</p>)}</div>}
    </section>
    <section className="panel"><h2>Method</h2><p className="muted">{data?.methodology || "Risk calculations use your recorded holdings and completed daily closes."}</p><a className="ticker-link" href="https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size" target="_blank" rel="noreferrer">Position sizing principles · CME Group</a></section>
  </>;
}
