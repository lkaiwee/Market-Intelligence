"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ErrorBox } from "@/components/ErrorBox";
import { PageHeader } from "@/components/PageHeader";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Trade = { id: number; ticker: string; side: string; status: string; entry_date: string; entry_price: number; quantity: number; exit_date: string | null; exit_price: number | null; fees: number; initial_stop: number | null; thesis: string; tags: string[]; gross_pnl: number | null; net_pnl: number | null; initial_risk: number | null; r_multiple: number | null; return_on_entry_notional_pct: number | null; holding_days: number | null };
type Summary = { closed_trades: number; wins: number; losses: number; breakeven: number; net_pnl: number; win_rate_pct: number | null; profit_factor: number | null; profit_factor_note: string | null; expectancy_per_trade: number | null; average_win: number | null; average_loss: number | null; average_r_multiple: number | null; trades_with_r_multiple: number; closed_trade_fees: number; average_holding_days: number | null };
type Analytics = Summary & { open_trades: number; total_trades: number; max_closed_pnl_drawdown: number; pnl_curve: { date: string; daily_closed_pnl: number; cumulative_closed_pnl: number; drawdown_amount: number }[]; monthly: (Summary & { month: string })[]; groups: (Summary & { dimension: string; name: string })[]; methodology: string };
type TradeList = { trades: Trade[]; total: number; limit: number; offset: number };
const emptyForm = { ticker: "", side: "long", entry_date: "", entry_price: "", quantity: "", exit_date: "", exit_price: "", fees: "0", initial_stop: "", thesis: "", tags: "" };
const money = (n: number | null) => n === null ? "—" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const pct = (n: number | null) => n === null ? "—" : `${n.toFixed(2)}%`;

function PnlCurve({ rows }: { rows: Analytics["pnl_curve"] }) {
  if (!rows.length) return <p className="muted">Close a recorded trade to build the P&amp;L curve.</p>;
  const values = [0, ...rows.map(r => r.cumulative_closed_pnl)];
  const low = Math.min(...values), high = Math.max(...values), range = high - low || 1;
  const y = (v: number) => 180 - (v - low) / range * 150;
  const points = values.map((v, i) => `${70 + i / (values.length - 1) * 690},${y(v)}`).join(" ");
  return <figure style={{ margin: 0 }}><svg viewBox="0 0 800 220" role="img" aria-label={`Cumulative closed trade P&L, beginning at zero and ending at ${money(values[values.length - 1])}`} style={{ width: "100%", maxHeight: 300 }}><line x1="70" x2="760" y1={y(0)} y2={y(0)} stroke="var(--muted)" strokeDasharray="4 4" /><polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="3" /><text x="4" y="35" fill="var(--muted)" fontSize="11">{money(high)}</text><text x="4" y="183" fill="var(--muted)" fontSize="11">{money(low)}</text><text x="70" y="212" fill="var(--muted)" fontSize="11">Initial $0</text><text x="760" y="212" textAnchor="end" fill="var(--muted)" fontSize="11">{rows[rows.length - 1].date}</text></svg><figcaption className="muted">Closed P&amp;L by exit date. The curve begins at zero; it is not account NAV and excludes open-position marks, deposits and withdrawals.</figcaption></figure>;
}

export default function JournalPage() {
  const [list, setList] = useState<TradeList | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);
  const revision = useRef(0);
  async function load(pageOffset: number, filter: string) {
    const request = ++revision.current; setLoading(true);
    try {
      const [rows, stats] = await Promise.all([apiGet<TradeList>(`/api/journal?limit=100&offset=${pageOffset}&status=${filter}`), apiGet<Analytics>("/api/journal/analytics")]);
      if (request === revision.current) { setList(rows); setAnalytics(stats); }
    } catch (e) { if (request === revision.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (request === revision.current) setLoading(false); }
  }
  useEffect(() => { load(offset, status); return () => { revision.current += 1; }; }, [offset, status]);
  function field(key: keyof typeof form, value: string) { setForm(s => ({ ...s, [key]: value })); }
  function edit(trade: Trade) {
    setEditing(trade.id); setMessage(null); setError(null);
    setForm({ ticker: trade.ticker, side: trade.side, entry_date: trade.entry_date, entry_price: String(trade.entry_price), quantity: String(trade.quantity), exit_date: trade.exit_date || "", exit_price: trade.exit_price === null ? "" : String(trade.exit_price), fees: String(trade.fees), initial_stop: trade.initial_stop === null ? "" : String(trade.initial_stop), thesis: trade.thesis, tags: trade.tags.join(", ") });
    document.getElementById("journal-form")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null);
    const payload = { ticker: form.ticker.trim().toUpperCase(), side: form.side, entry_date: form.entry_date, entry_price: form.entry_price, quantity: form.quantity, exit_date: form.exit_date || null, exit_price: form.exit_price || null, fees: form.fees, initial_stop: form.initial_stop || null, thesis: form.thesis, tags: form.tags.split(",").map(t => t.trim()).filter(Boolean) };
    try {
      if (editing !== null) await apiPut<Trade>(`/api/journal/${editing}`, payload); else await apiPost<Trade>("/api/journal", payload);
      setMessage(editing === null ? "Trade recorded in your journal." : "Journal trade updated."); setEditing(null); setForm(emptyForm); setOffset(0); await load(0, status);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function remove(trade: Trade) {
    if (!window.confirm(`Delete journal trade #${trade.id} (${trade.ticker})? This removes its performance history.`)) return;
    setBusy(true); setError(null); setMessage(null);
    try { await apiDelete(`/api/journal/${trade.id}`); if (editing === trade.id) { setEditing(null); setForm(emptyForm); } setMessage("Journal trade deleted."); setOffset(0); await load(0, status); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  return <>
    <PageHeader title="Trade Journal & Performance" subtitle="Record your decisions and completed trades, then measure outcomes after fees." />
    {error && <ErrorBox message={error} />}{message && <div className="job-result SUCCESS" role="status"><strong>{message}</strong></div>}
    {analytics && <section className="metric-grid">
      <div className="metric-card"><span className="eyebrow">Closed net P&L</span><strong className={analytics.net_pnl < 0 ? "negative" : "positive"}>{money(analytics.net_pnl)}</strong><span className="muted">{analytics.closed_trades} closed / {analytics.open_trades} open trades</span></div>
      <div className="metric-card"><span className="eyebrow">Win rate</span><strong>{pct(analytics.win_rate_pct)}</strong><span className="muted">{analytics.wins} wins · {analytics.losses} losses · {analytics.breakeven} flat</span></div>
      <div className="metric-card"><span className="eyebrow">Profit factor</span><strong>{analytics.profit_factor?.toFixed(2) ?? "—"}</strong><span className="muted">{analytics.profit_factor_note || "Net winning P&L / absolute net losing P&L"}</span></div>
      <div className="metric-card"><span className="eyebrow">Expectancy / trade</span><strong>{money(analytics.expectancy_per_trade)}</strong><span className="muted">Mean net P&L across all closed trades</span></div>
    </section>}
    <section className="panel" id="journal-form"><h2>{editing === null ? "Record a trade" : `Edit journal trade #${editing}`}</h2><p className="muted">Record actual trades in USD. Leave both exit fields empty for an open trade. For partial exits, record separate lots and allocate fees. Journal entries are independent of portfolio holdings.</p>
      <form onSubmit={save}><fieldset disabled={busy} style={{ padding: 0, border: 0, margin: 0 }}><div className="research-form">
        <label>Ticker<input value={form.ticker} onChange={e => field("ticker", e.target.value)} maxLength={16} required placeholder="Ticker" /></label>
        <label>Direction<select value={form.side} onChange={e => field("side", e.target.value)}><option value="long">Long</option><option value="short">Short</option></select></label>
        <label>Entry date (UTC)<input type="date" value={form.entry_date} onChange={e => field("entry_date", e.target.value)} required /></label>
        <label>Entry price<input type="number" min="0.000001" step="0.000001" value={form.entry_price} onChange={e => field("entry_price", e.target.value)} required /></label>
        <label>Shares / lot quantity<input type="number" min="0.000001" step="0.000001" value={form.quantity} onChange={e => field("quantity", e.target.value)} required /></label>
        <label>Initial stop (optional)<input type="number" min="0.000001" step="0.000001" value={form.initial_stop} onChange={e => field("initial_stop", e.target.value)} placeholder="Needed for R multiple" /></label>
        <label>Exit date (UTC, optional)<input type="date" value={form.exit_date} onChange={e => field("exit_date", e.target.value)} /></label>
        <label>Exit price (optional)<input type="number" min="0.000001" step="0.000001" value={form.exit_price} onChange={e => field("exit_price", e.target.value)} /></label>
        <label>Total fees for this lot (USD)<input type="number" min="0" step="0.01" value={form.fees} onChange={e => field("fees", e.target.value)} required /></label>
        <label>Tags (comma separated)<input value={form.tags} onChange={e => field("tags", e.target.value)} placeholder="e.g. breakout, earnings" /></label>
        <label style={{ gridColumn: "1 / -1" }}>Thesis, execution & lessons<textarea rows={3} maxLength={10000} value={form.thesis} onChange={e => field("thesis", e.target.value)} placeholder="Why you entered, what changed, and what you learned" /></label>
      </div><div className="research-actions"><button className="button primary" type="submit">{busy ? "Saving…" : editing === null ? "Record trade" : "Save trade changes"}</button>{editing !== null && <button className="button" type="button" onClick={() => { setEditing(null); setForm(emptyForm); }}>Cancel edit</button>}</div></fieldset></form>
    </section>
    <section className="panel"><div className="panel-heading"><h2>Journal entries</h2><div className="research-actions"><label>Show <select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }} disabled={busy}><option value="all">All trades</option><option value="open">Open trades</option><option value="closed">Closed trades</option></select></label><button className="button" onClick={() => load(offset, status)} disabled={loading || busy}>Refresh</button></div></div>
      {loading && <p className="muted" role="status">Loading journal…</p>}
      {list && !list.trades.length && <p className="muted">No {status === "all" ? "recorded" : status} trades. Use the form above to add your actual trades.</p>}
      {!!list?.trades.length && <div className="table-wrap"><table><thead><tr><th>Trade</th><th>Entry</th><th>Exit</th><th>Quantity / fees</th><th>Net P&L</th><th>R multiple</th><th>Notes / tags</th><th>Actions</th></tr></thead><tbody>{list.trades.map(t => <tr key={t.id}><td><strong>{t.ticker}</strong><div className="subcell">#{t.id} · {t.side} · {t.status}</div></td><td>{money(t.entry_price)}<div className="subcell">{t.entry_date}</div></td><td>{money(t.exit_price)}<div className="subcell">{t.exit_date || "Open"}</div></td><td>{t.quantity.toLocaleString("en-US", { maximumFractionDigits: 6 })}<div className="subcell">Fees {money(t.fees)}</div></td><td className={(t.net_pnl ?? 0) < 0 ? "negative" : "positive"}>{money(t.net_pnl)}<div className="subcell">{pct(t.return_on_entry_notional_pct)} on entry notional</div></td><td>{t.r_multiple === null ? "—" : `${t.r_multiple.toFixed(2)}R`}<div className="subcell">Initial risk {money(t.initial_risk)}</div></td><td><details><summary>{t.tags.join(", ") || "Notes"}</summary><p style={{ whiteSpace: "pre-wrap", maxWidth: 340 }}>{t.thesis || "No thesis recorded."}</p></details></td><td><div className="research-actions"><button className="button" onClick={() => edit(t)} disabled={busy}>Edit / close</button><button className="button" onClick={() => remove(t)} disabled={busy}>Delete</button></div></td></tr>)}</tbody></table></div>}
      {list && <div className="research-actions" style={{ marginTop: 16 }}><span className="muted">{list.total ? `${list.offset + 1}–${list.offset + list.trades.length} of ${list.total}` : "0 trades"}</span><button className="button" disabled={offset === 0 || busy || loading} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous</button><button className="button" disabled={offset + 100 >= list.total || busy || loading} onClick={() => setOffset(offset + 100)}>Next</button></div>}
    </section>
    {analytics && <>
      <section className="panel"><h2>Closed P&L curve</h2><p className="muted">Analytics use all recorded trades, regardless of the table filter.</p><PnlCurve rows={analytics.pnl_curve} /><div className="metric-grid" style={{ marginTop: 20 }}>
        <div className="metric-card"><span className="eyebrow">Maximum P&L drawdown</span><strong>{money(analytics.max_closed_pnl_drawdown)}</strong><span className="muted">Dollar decline from previous closed-P&L peak</span></div>
        <div className="metric-card"><span className="eyebrow">Average R multiple</span><strong>{analytics.average_r_multiple === null ? "—" : `${analytics.average_r_multiple.toFixed(2)}R`}</strong><span className="muted">{analytics.trades_with_r_multiple}/{analytics.closed_trades} trades have initial risk</span></div>
        <div className="metric-card"><span className="eyebrow">Average win / loss</span><strong>{money(analytics.average_win)} / {money(analytics.average_loss)}</strong><span className="muted">Loss shown as a positive magnitude</span></div>
        <div className="metric-card"><span className="eyebrow">Closed trade fees</span><strong>{money(analytics.closed_trade_fees)}</strong><span className="muted">Mean holding time {analytics.average_holding_days?.toFixed(1) ?? "—"} calendar days</span></div>
      </div></section>
      {!!analytics.monthly.length && <section className="panel"><h2>Monthly closed performance</h2><div className="table-wrap"><table><thead><tr><th>Exit month</th><th>Trades</th><th>Net P&L</th><th>Win rate</th><th>Expectancy</th></tr></thead><tbody>{analytics.monthly.map(m => <tr key={m.month}><td>{m.month}</td><td>{m.closed_trades}</td><td>{money(m.net_pnl)}</td><td>{pct(m.win_rate_pct)}</td><td>{money(m.expectancy_per_trade)}</td></tr>)}</tbody></table></div></section>}
      {!!analytics.groups.length && <section className="panel"><h2>Performance by direction & tag</h2><p className="muted">A trade may have multiple tags; tag totals overlap.</p><div className="table-wrap"><table><thead><tr><th>Group</th><th>Trades</th><th>Net P&L</th><th>Win rate</th><th>Expectancy</th><th>Average R</th></tr></thead><tbody>{analytics.groups.map(g => <tr key={`${g.dimension}:${g.name}`}><td>{g.name}<div className="subcell">{g.dimension}</div></td><td>{g.closed_trades}</td><td>{money(g.net_pnl)}</td><td>{pct(g.win_rate_pct)}</td><td>{money(g.expectancy_per_trade)}</td><td>{g.average_r_multiple === null ? "—" : `${g.average_r_multiple.toFixed(2)}R`}</td></tr>)}</tbody></table></div></section>}
      <section className="panel"><h2>Method</h2><p className="muted">{analytics.methodology}</p></section>
    </>}
  </>;
}
