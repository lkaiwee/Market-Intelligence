"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { ErrorBox } from "@/components/ErrorBox";
import { PageHeader } from "@/components/PageHeader";

type Period = { period_end: string; [key: string]: number | string | boolean | null };
type Quality = { ticker: string; cached: boolean; message?: string; company_name?: string;
  source?: string; source_url?: string; financial_currency?: string | null; fetched_at?: string;
  latest_period?: string | null; score?: number | null; score_note?: string;
  checks_met?: number; checks_available?: number; checks_total?: number;
  checks?: { metric: string; label: string; value: number | null; result: string }[];
  periods?: Period[]; warnings?: string[] };
const value = (n: unknown, digits = 2) => typeof n === "number" ? n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "—";
const metrics: { key: string; label: string; percent?: boolean; amount?: boolean; formula: string }[] = [
  { key: "revenue", label: "Revenue", amount: true, formula: "Reported annual total revenue" },
  { key: "net_income", label: "Net income", amount: true, formula: "Reported annual net income" },
  { key: "operating_cashflow", label: "Operating cash flow", amount: true, formula: "Reported annual operating cash flow" },
  { key: "capex", label: "Capital expenditure", amount: true, formula: "Reported signed capital expenditure" },
  { key: "free_cash_flow", label: "Free cash flow", amount: true, formula: "Operating cash flow − absolute capital expenditure" },
  { key: "net_borrowing", label: "Net borrowing", amount: true, formula: "Reported net issuance / payments of debt; the valuation DCF separately assumes zero net borrowing" },
  { key: "assets", label: "Closing assets", amount: true, formula: "Reported fiscal year-end total assets" },
  { key: "average_assets", label: "Average assets", amount: true, formula: "(Current + prior annual closing assets) / 2" },
  { key: "cfo_to_net_income", label: "CFO / net income", formula: "Operating cash flow / positive net income" },
  { key: "accruals_to_average_assets", label: "Accruals / average assets", percent: true, formula: "(Net income − operating cash flow) / average annual assets" },
  { key: "cash_conversion_margin", label: "Cash conversion margin", percent: true, formula: "Operating cash flow / revenue" },
  { key: "fcf_margin", label: "Free cash flow margin", percent: true, formula: "Free cash flow / revenue" },
  { key: "net_margin", label: "Net margin", percent: true, formula: "Net income / revenue" },
  { key: "current_ratio", label: "Current ratio", formula: "Current assets / current liabilities" },
  { key: "debt_to_equity", label: "Debt / equity", formula: "Total debt / positive stockholders’ equity" },
  { key: "interest_coverage", label: "Operating interest coverage", formula: "Operating income / absolute interest expense" },
  { key: "stock_compensation_to_revenue", label: "Stock compensation / revenue", percent: true, formula: "Stock-based compensation / revenue" },
  { key: "revenue_growth_yoy", label: "Annual revenue growth", percent: true, formula: "Current revenue / previous annual revenue − 1" },
  { key: "diluted_share_growth_yoy", label: "Annual diluted-share growth", percent: true, formula: "Current diluted average shares / previous annual diluted average shares − 1" },
];

export default function QualityPage() {
  const [ticker, setTicker] = useState("AAPL");
  const [data, setData] = useState<Quality | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const request = useRef(0);
  const mounted = useRef(true);
  async function load(symbol: string, refresh = false) {
    symbol = symbol.trim().toUpperCase();
    if (!/^[A-Z0-9][A-Z0-9.^=-]{0,15}$/.test(symbol)) { setError("Enter a valid ticker."); return; }
    const current = ++request.current;
    setBusy(true); setError(null);
    try {
      const result = refresh ? await apiPost<Quality>(`/api/quality/${encodeURIComponent(symbol)}/refresh`) : await apiGet<Quality>(`/api/quality/${encodeURIComponent(symbol)}`);
      if (mounted.current && request.current === current) { setData(result); setTicker(symbol); }
    } catch (e) { if (mounted.current && request.current === current) setError(e instanceof Error ? e.message : "Could not load financial statements."); }
    finally { if (mounted.current && request.current === current) setBusy(false); }
  }
  useEffect(() => {
    mounted.current = true;
    const symbol = new URLSearchParams(window.location.search).get("ticker") || "AAPL";
    setTicker(symbol); void load(symbol);
    return () => { mounted.current = false; request.current += 1; };
  }, []);
  function submit(event: FormEvent) { event.preventDefault(); void load(ticker); }
  return <>
    <PageHeader title="Earnings Quality" subtitle="Compare reported profit with cash generation, balance-sheet strength and dilution." />
    {error && <ErrorBox message={error} />}
    <form className="panel" onSubmit={submit}>
      <div className="panel-heading"><div><span className="eyebrow">8.1 · Reported financials</span><h2>Annual statement review</h2></div></div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <label style={{ display: "grid", gap: 8, fontSize: 12 }}>Ticker<input required maxLength={16} disabled={busy} value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} style={{ width: 170, padding: 10, border: "1px solid var(--border)", borderRadius: 8, background: "var(--bg)", color: "var(--text)" }} /></label>
        <button className="button" disabled={busy} type="submit">Load cached statements</button>
        <button className="button primary" disabled={busy} type="button" onClick={() => void load(ticker, true)}>{busy ? "Loading…" : "Refresh annual statements"}</button>
      </div>
      <p className="muted">Fetch real annual statements once and reuse the stored report. Missing source metrics remain unavailable. A refresh may take up to 90 seconds on the free API.</p>
    </form>
    {data && !data.cached && <div className="panel"><h2>{data.ticker}</h2><p>{data.message}</p></div>}
    {data?.cached && <>
      <div className="panel"><strong>{data.ticker} · {data.company_name || "Annual financial statements"}</strong><p className="muted">Latest aligned fiscal year: {data.latest_period || "Unavailable"} · Reporting currency: {data.financial_currency || "Not supplied by provider"} · Refreshed: {data.fetched_at ? new Date(data.fetched_at).toLocaleString() : "Unknown"}</p><a className="text-link" href={data.source_url} target="_blank" rel="noreferrer">{data.source}</a></div>
      <div className="metric-grid">
        <div className="metric-card"><span className="eyebrow">Financial checks</span><strong>{data.checks_met} / {data.checks_available}</strong><span className="muted">Available checks meeting thresholds</span></div>
        <div className="metric-card"><span className="eyebrow">Data coverage</span><strong>{data.checks_available} / {data.checks_total}</strong><span className="muted">Checks supported by source data</span></div>
        <div className="metric-card"><span className="eyebrow">Checklist score</span><strong>{data.score == null ? "Insufficient coverage" : `${data.score} / 100`}</strong><span className="muted">Descriptive, sector-neutral checklist</span></div>
        <div className="metric-card"><span className="eyebrow">Fiscal periods</span><strong>{data.periods?.length || 0}</strong><span className="muted">Annual, with exact date alignment</span></div>
      </div>
      <div className="panel"><h2>Latest aligned year: cash and balance-sheet checks</h2><div className="table-wrap"><table><thead><tr><th>Check</th><th>Reported ratio</th><th>Result</th></tr></thead><tbody>{data.checks?.map(check => <tr key={check.metric}><td>{check.label}</td><td>{value(check.value)}</td><td style={{ color: check.result === "met" ? "var(--accent)" : check.result === "review" ? "var(--amber)" : "var(--muted)" }}>{check.result === "met" ? "Meets threshold" : check.result === "review" ? "Review context" : "Unavailable"}</td></tr>)}</tbody></table></div><p className="muted">{data.score_note} Ratios in this checklist are raw decimal values.</p></div>
      <div className="panel"><h2>Annual trends and calculation trail</h2><p className="muted">Statement amounts are shown in millions of {data.financial_currency || "the provider’s reporting currency"}. Ratios use the underlying full amounts. Hover a metric for its formula.</p><div className="table-wrap"><table><thead><tr><th>Metric</th>{data.periods?.map(period => <th key={period.period_end}>{period.period_end}</th>)}</tr></thead><tbody>{metrics.map(metric => <tr key={metric.key}><td title={metric.formula}>{metric.label}{metric.amount ? " (M)" : ""}</td>{data.periods?.map(period => { const raw = period[metric.key]; const displayed = typeof raw === "number" ? raw * (metric.percent ? 100 : metric.amount ? 1e-6 : 1) : null; return <td key={period.period_end}>{value(displayed)}{displayed !== null && metric.percent ? "%" : ""}</td>; })}</tr>)}</tbody></table></div></div>
      <div className="panel"><h2>Interpretation and limitations</h2><ul>{data.warnings?.map((warning, i) => <li key={i} style={{ marginBottom: 10 }}>{warning}</li>)}</ul><p className="muted">Accruals use average assets from adjacent annual balance sheets. Share growth uses annual diluted weighted-average shares. These differ from current shares outstanding used for valuation.</p><a className="text-link" href="https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements" target="_blank" rel="noreferrer">SEC guide to reading financial statements</a></div>
    </>}
  </>;
}
