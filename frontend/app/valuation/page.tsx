"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import { ErrorBox } from "@/components/ErrorBox";
import { PageHeader } from "@/components/PageHeader";

type Model = {
  growth_pct: number; discount_pct: number; terminal_growth_pct: number; years: number;
  margin_of_safety_pct: number; earnings_multiple: number; earnings_growth_pct: number;
  base_cash_flow_override: number | null; shares_override: number | null;
  eps_override: number | null; cash_flow_currency: string;
};
type Valuation = {
  context: { ticker: string; current_price: number | null; price_date: string | null;
    fiscal_period_end: string | null; statements_fetched_at: string | null;
    fundamentals_updated_at: string | null; shares_source: string | null;
    base_cash_flow_source: string | null; source_url: string; financial_currency: string | null; };
  quote_currency: string | null; inputs: Model; used_cash_flow: number | null; used_shares: number | null;
  dcf: { fair_value_per_share: number; buy_below_with_margin_of_safety: number; upside_pct: number | null;
    terminal_value_share_pct: number; projections: { year: number; cash_flow: number; present_value: number }[]; } | null;
  dcf_unavailable_reason: string | null;
  scenarios: { name: string; growth_pct: number; discount_pct: number; fair_value: number }[];
  sensitivity: { discount_pct: number; terminal_growth_pct: number; fair_value: number | null }[];
  earnings_multiple: { base_eps: number; next_year_eps: number; multiple: number; fair_value: number; method: string } | null;
  earnings_unavailable_reason: string | null; methodology: string; methodology_source: string; warnings: string[];
};
const defaults: Model = { growth_pct: 8, discount_pct: 10, terminal_growth_pct: 2.5, years: 5,
  margin_of_safety_pct: 20, earnings_multiple: 20, earnings_growth_pct: 5,
  base_cash_flow_override: null, shares_override: null, eps_override: null, cash_flow_currency: "USD" };
const fieldStyle = { display: "grid", gap: 7, fontSize: 12, color: "var(--muted)" } as const;
const inputStyle = { width: "100%", padding: "10px 12px", background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 8 };
const formStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(175px, 1fr))", gap: 16 };
const num = (n: number | null | undefined, digits = 2) => n == null ? "—" : n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export default function ValuationPage() {
  const [ticker, setTicker] = useState("AAPL");
  const [model, setModel] = useState<Model>(defaults);
  const [result, setResult] = useState<Valuation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const mounted = useRef(true);
  const [overrides, setOverrides] = useState({ cashFlow: "", shares: "", eps: "" });
  useEffect(() => {
    mounted.current = true;
    const current = ++revision.current;
    setBusy(true);
    apiGet<Valuation>("/api/valuation/AAPL").then(data => {
      if (mounted.current && revision.current === current) setResult(data);
    }).catch(e => { if (mounted.current && revision.current === current) setError(String(e.message || e)); })
      .finally(() => { if (mounted.current && revision.current === current) setBusy(false); });
    return () => { mounted.current = false; revision.current += 1; };
  }, []);
  async function run(refresh = false) {
    const symbol = ticker.trim().toUpperCase();
    if (!/^[A-Z0-9][A-Z0-9.^=-]{0,15}$/.test(symbol)) { setError("Enter a valid ticker."); return; }
    if (model.discount_pct <= model.terminal_growth_pct) { setError("Cost of equity must exceed terminal growth."); return; }
    const payload: Model = { ...model,
      base_cash_flow_override: overrides.cashFlow.trim() ? Number(overrides.cashFlow) * 1e6 : null,
      shares_override: overrides.shares.trim() ? Number(overrides.shares) * 1e6 : null,
      eps_override: overrides.eps.trim() ? Number(overrides.eps) : null };
    const current = ++revision.current;
    setBusy(true); setError(null);
    try {
      if (refresh) await apiPost(`/api/quality/${encodeURIComponent(symbol)}/refresh`);
      const data = await apiPost<Valuation>(`/api/valuation/${encodeURIComponent(symbol)}`, payload);
      if (mounted.current && current === revision.current) { setResult(data); setTicker(symbol); }
    } catch (e) { if (mounted.current && current === revision.current) setError(e instanceof Error ? e.message : "Valuation request failed."); }
    finally { if (mounted.current && current === revision.current) setBusy(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); void run(); }
  const currency = result?.quote_currency || "quote currency";
  const cash = (n: number | null | undefined) => `${num(n)} ${currency}`;
  const assumptions: { key: keyof Model; label: string; min: number; max: number; step: number }[] = [
    { key: "growth_pct", label: "Annual cash-flow growth (%)", min: -50, max: 100, step: .5 },
    { key: "discount_pct", label: "Cost of equity (%)", min: 1, max: 60, step: .5 },
    { key: "terminal_growth_pct", label: "Terminal growth (%)", min: -5, max: 6, step: .25 },
    { key: "years", label: "Projection years", min: 1, max: 15, step: 1 },
    { key: "margin_of_safety_pct", label: "Margin of safety (%)", min: 0, max: 80, step: 1 },
    { key: "earnings_multiple", label: "Chosen earnings multiple (×)", min: 1, max: 100, step: 1 },
    { key: "earnings_growth_pct", label: "Next-year EPS growth (%)", min: -80, max: 100, step: 1 },
  ];
  const rates = result ? Array.from(new Set(result.sensitivity.map(cell => cell.discount_pct))) : [];
  const terminalRates = result ? Array.from(new Set(result.sensitivity.map(cell => cell.terminal_growth_pct))) : [];
  return <>
    <PageHeader title="Fair Value & Valuation" subtitle="Model the assumptions behind a price with equity cash flows and earnings multiples." />
    {error && <ErrorBox message={error} />}
    <form className="panel" onSubmit={submit}>
      <div className="panel-heading"><div><span className="eyebrow">8.0 · Scenario workbench</span><h2>Choose your assumptions</h2></div></div>
      <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
        <div style={formStyle}>
          <label style={fieldStyle}>Ticker<input style={inputStyle} required maxLength={16} value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} /></label>
          {assumptions.map(field => <label key={field.key} style={fieldStyle}>{field.label}<input style={inputStyle} type="number" required min={field.min} max={field.max} step={field.step} value={model[field.key] ?? ""} onChange={e => setModel(current => ({ ...current, [field.key]: Number(e.target.value) }))} /></label>)}
          <label style={fieldStyle}>Cash-flow override (millions)<input style={inputStyle} type="number" step="any" placeholder="Use annual statements" value={overrides.cashFlow} onChange={e => setOverrides(v => ({ ...v, cashFlow: e.target.value }))} /></label>
          <label style={fieldStyle}>Shares override (millions)<input style={inputStyle} type="number" min="0.000001" step="any" placeholder="Use provider shares" value={overrides.shares} onChange={e => setOverrides(v => ({ ...v, shares: e.target.value }))} /></label>
          <label style={fieldStyle}>EPS override (per share)<input style={inputStyle} type="number" step="any" placeholder="Use price / trailing P/E" value={overrides.eps} onChange={e => setOverrides(v => ({ ...v, eps: e.target.value }))} /></label>
          <label style={fieldStyle}>Override currency<input style={inputStyle} pattern="[A-Z]{3}" maxLength={3} value={model.cash_flow_currency} onChange={e => setModel(v => ({ ...v, cash_flow_currency: e.target.value.toUpperCase() }))} /></label>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 20 }}>
          <button className="button primary" type="submit">{busy ? "Calculating…" : "Calculate valuation"}</button>
          <button className="button" type="button" onClick={() => void run(true)}>Refresh annual statements & calculate</button>
        </div>
      </fieldset>
      <p className="muted">Overrides are scenario inputs. Cash flow is after interest and assumes zero net borrowing. Annual statements are cached until you refresh. Results below retain the last submitted assumptions.</p>
    </form>
    {result && <>
      <div className="panel"><strong>{result.context.ticker}</strong><p className="muted">Close: {cash(result.context.current_price)} · {result.context.price_date || "No stored close"}. Fiscal year: {result.context.fiscal_period_end || "Unavailable"}. Statement currency: {result.context.financial_currency || "Unknown"}.</p>
        <p className="muted">Statements retrieved: {result.context.statements_fetched_at ? new Date(result.context.statements_fetched_at).toLocaleString() : "Not yet"}. Fundamentals: {result.context.fundamentals_updated_at ? new Date(result.context.fundamentals_updated_at).toLocaleString() : "Unavailable"}.</p>
        <p className="muted">Model cash-flow base: {num(result.used_cash_flow == null ? null : result.used_cash_flow / 1e6)} million {currency}. Shares: {num(result.used_shares == null ? null : result.used_shares / 1e6)} million. {result.inputs.shares_override !== null ? "User share override." : result.context.shares_source}</p>
        <Link className="text-link" href={`/quality/?ticker=${encodeURIComponent(result.context.ticker)}`}>Inspect earnings quality →</Link>
      </div>
      <div className="metric-grid">
        <div className="metric-card"><span className="eyebrow">Equity DCF / share</span><strong>{cash(result.dcf?.fair_value_per_share)}</strong><span className="muted">Conditional present value</span></div>
        <div className="metric-card"><span className="eyebrow">With safety margin</span><strong>{cash(result.dcf?.buy_below_with_margin_of_safety)}</strong><span className="muted">{result.inputs.margin_of_safety_pct}% below model value</span></div>
        <div className="metric-card"><span className="eyebrow">DCF vs current price</span><strong>{num(result.dcf?.upside_pct)}%</strong><span className="muted">Model difference, not expected return</span></div>
        <div className="metric-card"><span className="eyebrow">EPS × multiple</span><strong>{cash(result.earnings_multiple?.fair_value)}</strong><span className="muted">One-year scenario price</span></div>
      </div>
      {result.dcf_unavailable_reason && <div className="panel"><p>{result.dcf_unavailable_reason}</p></div>}
      {result.scenarios.length > 0 && <div className="panel"><div className="panel-heading"><h2>Bear, base and bull scenarios</h2></div><div className="table-wrap"><table><thead><tr><th>Scenario</th><th>Growth</th><th>Cost of equity</th><th>Value / share</th></tr></thead><tbody>{result.scenarios.map(row => <tr key={row.name}><td>{row.name}</td><td>{num(row.growth_pct)}%</td><td>{num(row.discount_pct)}%</td><td>{cash(row.fair_value)}</td></tr>)}</tbody></table></div><p className="muted">Bear/bull shift annual growth by ±5 percentage points and cost of equity by ∓2 points. Scenario discount rates have a 0.5% floor and stay at least 0.5 percentage points above terminal growth.</p></div>}
      {result.dcf && <div className="panel"><div className="panel-heading"><h2>DCF sensitivity: cost of equity × terminal growth</h2></div><div className="table-wrap"><table><thead><tr><th>Cost of equity ↓ / terminal growth →</th>{terminalRates.map(rate => <th key={rate}>{num(rate)}%</th>)}</tr></thead><tbody>{rates.map(rate => <tr key={rate}><td>{num(rate)}%</td>{terminalRates.map(terminalRate => <td key={terminalRate}>{num(result.sensitivity.find(cell => cell.discount_pct === rate && cell.terminal_growth_pct === terminalRate)?.fair_value)}</td>)}</tr>)}</tbody></table></div><p className="muted">Values per share in {currency}; — means no valid positive discount-rate spread. Terminal value contributes {num(result.dcf.terminal_value_share_pct)}% of the base DCF.</p></div>}
      {result.dcf && <div className="panel"><h2>Annual cash-flow projections</h2><div className="table-wrap"><table><thead><tr><th>Year</th><th>Cash flow (millions)</th><th>Present value (millions)</th></tr></thead><tbody>{result.dcf.projections.map(p => <tr key={p.year}><td>{p.year}</td><td>{num(p.cash_flow / 1e6)}</td><td>{num(p.present_value / 1e6)}</td></tr>)}</tbody></table></div></div>}
      <div className="panel"><h2>Earnings-multiple model</h2>{result.earnings_multiple ? <p>Base EPS {cash(result.earnings_multiple.base_eps)} → next-year EPS {cash(result.earnings_multiple.next_year_eps)} × {result.earnings_multiple.multiple} = {cash(result.earnings_multiple.fair_value)}.</p> : <p>{result.earnings_unavailable_reason}</p>}<p className="muted">{result.earnings_multiple?.method}</p></div>
      <div className="panel"><h2>Method and data notes</h2><p>{result.methodology}</p><ul>{result.warnings.map((warning, i) => <li key={i} style={{ marginBottom: 10 }}>{warning}</li>)}</ul><a className="text-link" href={result.context.source_url} target="_blank" rel="noreferrer">Source statements</a> · <a className="text-link" href={result.methodology_source} target="_blank" rel="noreferrer">Equity valuation framework</a></div>
    </>}
  </>;
}
