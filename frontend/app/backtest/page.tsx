"use client";

import { FormEvent, useState } from "react";
import { apiPost } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ErrorBox } from "@/components/ErrorBox";
import { ResearchChart } from "@/components/ResearchChart";

type Trade = { entry_date: string; signal_date: string; exit_date: string; entry_price: number; exit_price: number; shares: number; pnl: number; fees: number; exit_reason: string };
type Result = { ticker: string; strategy: string; actual_start: string; actual_end: string; sessions: number; warmup_bars: number;
  metrics: Record<string, number | null>; equity_curve: { date: string; equity: number; benchmark: number; drawdown_pct: number }[];
  trades: Trade[]; open_position: { shares: number; entry_price: number; unrealized_pnl: number } | null; notes: string[] };
const fmt = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function BacktestPage() {
  const [ticker, setTicker] = useState("SPY"), [strategy, setStrategy] = useState("sma_trend");
  const [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [capital, setCapital] = useState("10000"), [allocation, setAllocation] = useState("95");
  const [fee, setFee] = useState("10"), [slip, setSlip] = useState("5");
  const [fast, setFast] = useState("20"), [slow, setSlow] = useState("50");
  const [breakout, setBreakout] = useState("20"), [exit, setExit] = useState("10");
  const [rsiEntry, setRsiEntry] = useState("30"), [rsiExit, setRsiExit] = useState("55");
  const [stop, setStop] = useState("2"), [target, setTarget] = useState("");
  const [data, setData] = useState<Result | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  async function run(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setData(null);
    try { setData(await apiPost<Result>("/api/backtest", { ticker: ticker.trim().toUpperCase(), strategy,
      start_date: start || null, end_date: end || null, initial_capital: Number(capital), allocation_pct: Number(allocation),
      commission_bps: Number(fee), slippage_bps: Number(slip), fast_period: Number(fast), slow_period: Number(slow),
      breakout_period: Number(breakout), exit_period: Number(exit), rsi_entry: Number(rsiEntry), rsi_exit: Number(rsiExit),
      stop_atr: stop ? Number(stop) : null, target_r: target ? Number(target) : null }));
    } catch (err) { setError(String(err)); } finally { setBusy(false); }
  }
  function download() {
    if (!data) return;
    const csv = ["date,equity,benchmark,drawdown_pct", ...data.equity_curve.map(row => `${row.date},${row.equity},${row.benchmark},${row.drawdown_pct}`)].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${data.ticker}-backtest.csv`; anchor.click(); URL.revokeObjectURL(url);
  }
  return <><PageHeader title="Backtesting Engine" subtitle="8.4 · Test transparent daily strategies against buy and hold." />
    <section className="panel"><p className="muted">Simulation inputs only. Uses stored history, with signals filled at the next available session open. No orders or portfolio changes.</p>
      <form onSubmit={run}><fieldset disabled={busy} className="research-form">
        <label>Ticker<input required maxLength={16} value={ticker} onChange={e => setTicker(e.target.value)} /></label>
        <label>Strategy<select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="sma_trend">SMA trend</option><option value="breakout">Channel breakout</option><option value="rsi_reversion">RSI mean reversion</option></select></label>
        <label>Start date (optional)<input type="date" value={start} onChange={e => setStart(e.target.value)} /></label><label>End date (optional)<input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
        <label>Simulated capital ($)<input type="number" required min="1" step="any" value={capital} onChange={e => setCapital(e.target.value)} /></label>
        <label>Allocation (%)<input type="number" required min="0.1" max="100" step="any" value={allocation} onChange={e => setAllocation(e.target.value)} /></label>
        <label>Commission each fill (bps)<input type="number" required min="0" max="500" step="any" value={fee} onChange={e => setFee(e.target.value)} /></label>
        <label>Slippage each fill (bps)<input type="number" required min="0" max="500" step="any" value={slip} onChange={e => setSlip(e.target.value)} /></label>
        {strategy === "sma_trend" && <><label>Fast SMA<input type="number" required min="2" max="150" value={fast} onChange={e => setFast(e.target.value)} /></label><label>Slow SMA<input type="number" required min="3" max="250" value={slow} onChange={e => setSlow(e.target.value)} /></label></>}
        {strategy === "breakout" && <><label>Breakout lookback<input type="number" required min="5" max="100" value={breakout} onChange={e => setBreakout(e.target.value)} /></label><label>Exit channel lookback<input type="number" required min="2" max="100" value={exit} onChange={e => setExit(e.target.value)} /></label></>}
        {strategy === "rsi_reversion" && <><label>Enter below RSI<input type="number" required min="5" max="50" value={rsiEntry} onChange={e => setRsiEntry(e.target.value)} /></label><label>Exit above RSI<input type="number" required min="50" max="95" value={rsiExit} onChange={e => setRsiExit(e.target.value)} /></label></>}
        <label>Stop ATR multiple (blank = off)<input type="number" min="0.1" max="10" step="any" value={stop} onChange={e => setStop(e.target.value)} /></label>
        <label>Target R multiple (optional)<input type="number" min="0.1" max="20" step="any" value={target} onChange={e => setTarget(e.target.value)} /></label>
      </fieldset><div className="research-actions"><button className="button" type="submit" disabled={busy}>{busy ? "Simulating…" : "Run backtest"}</button><span className="muted">100 basis points = 1%. SMA trend holds while fast &gt; slow; breakout enters above prior highs and exits below prior lows.</span></div></form>
    </section>{error && <ErrorBox message={error} />}
    {data && <><section className="metric-grid">{[["Total return", "total_return_pct", "%"], ["Buy & hold", "benchmark_return_pct", "%"], ["Max drawdown", "max_drawdown_pct", "%"], ["Sharpe (zero rate)", "sharpe_zero_rate", ""], ["Closed trades", "closed_trades", ""], ["Win rate", "win_rate_pct", "%"], ["Profit factor", "profit_factor", ""], ["Fees paid", "fees_paid", " USD"]].map(([label, key, unit]) => <div className="metric-card" key={key}><span className="eyebrow">{label}</span><strong>{fmt(data.metrics[key])}{data.metrics[key] == null ? "" : unit}</strong></div>)}</section>
      <section className="panel"><div className="panel-heading"><div><h2>{data.ticker} · {data.actual_start} to {data.actual_end}</h2><p className="muted">{data.sessions} simulated sessions · {data.warmup_bars} prior bars · Ending equity ${fmt(data.metrics.final_equity)}</p></div><button className="button" onClick={download}>Export curve CSV</button></div><ResearchChart points={data.equity_curve} />
        <p className="muted">Annualized return {fmt(data.metrics.annualized_return_pct)}% · volatility {fmt(data.metrics.annualized_volatility_pct)}% · exposure {fmt(data.metrics.exposure_pct)}% · closed-trade expectancy ${fmt(data.metrics.expectancy)}</p>
        {data.open_position && <p>Open at period end: {data.open_position.shares} shares entered at ${fmt(data.open_position.entry_price)}; unrealized P&amp;L ${fmt(data.open_position.unrealized_pnl)}.</p>}</section>
      <section className="panel"><h2>Closed trades</h2>{!data.trades.length ? <p>No completed trades in this run. Check the open position and equity curve.</p> : <div className="table-wrap"><table><thead><tr><th>Signal / entry</th><th>Exit</th><th>Shares</th><th>Entry / exit</th><th>Net P&amp;L</th><th>Reason</th></tr></thead><tbody>{data.trades.map((trade, index) => <tr key={index}><td>{trade.signal_date}<div className="muted">Filled {trade.entry_date}</div></td><td>{trade.exit_date}</td><td>{trade.shares}</td><td>${fmt(trade.entry_price)} / ${fmt(trade.exit_price)}</td><td>${fmt(trade.pnl)}<div className="muted">Fees ${fmt(trade.fees)}</div></td><td>{trade.exit_reason}</td></tr>)}</tbody></table></div>}</section>
      <section className="panel"><h2>Execution model & limitations</h2>{data.notes.map(note => <p className="muted" key={note}>{note}</p>)}</section>
    </>}
  </>;
}
