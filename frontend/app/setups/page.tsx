"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";

type Setup = { id: string; name: string; matched: boolean; score: number; criteria: string };
type Row = { ticker: string; company_name: string; sector: string; status: string; latest_date?: string;
  price: number; rsi: number | null; atr: number | null; volume_ratio: number | null; relative_strength_63d_pp: number | null;
  entry_reference: number; stop_reference: number; target_2r: number; score: number; setups: Setup[] };
type Scan = { as_of: string; universe_size: number; scanned: number; current_series: number; results: Row[]; unavailable: Row[]; notes: string[] };
const fmt = (value: number | null | undefined) => value == null ? "—" : value.toFixed(2);

export default function SetupsPage() {
  const [data, setData] = useState<Scan | null>(null);
  const [setup, setSetup] = useState("ALL");
  const [matches, setMatches] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setBusy(true); setError(null);
    apiGet<Scan>(`/api/setups?setup=${setup}&matches_only=${matches}`).then(value => {
      if (active) setData(value);
    }).catch(err => { if (active) setError(String(err)); }).finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [setup, matches, revision]);
  return <>
    <PageHeader title="Technical Setup Scanner" subtitle="7.9 · Breakouts, trend pullbacks, volatility compression and oversold recovery." />
    <section className="panel"><div className="research-actions">
      <label>Setup <select aria-label="Setup filter" value={setup} onChange={e => setSetup(e.target.value)}>
        <option value="ALL">All setups</option><option value="BREAKOUT">20-session breakout</option><option value="PULLBACK">Trend pullback</option><option value="SQUEEZE">Volatility compression</option><option value="REVERSAL">Oversold recovery</option>
      </select></label>
      <label><input type="checkbox" checked={matches} onChange={e => setMatches(e.target.checked)} /> Complete matches only</label>
      <button className="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>{busy ? "Scanning…" : "Scan stored prices"}</button>
    </div><p className="muted">Uses your enabled stock universe. Refresh market prices in System to update the underlying data.</p></section>
    {error && <ErrorBox message={error} />}
    {!data && busy && <Loading />}
    {data && <>
      <section className="metric-grid">
        {[ ["Completed session", data.as_of], ["Current series", `${data.current_series}/${data.scanned}`], ["Results", String(data.results.length)], ["Unavailable", String(data.unavailable.length)] ].map(([label, value]) => <div className="metric-card" key={label}><span className="eyebrow">{label}</span><strong>{value}</strong></div>)}
      </section>
      <section className="panel"><div className="panel-heading"><h2>Setups & planning levels</h2></div>
        {!data.results.length ? <p>No complete matches for these filters. Turn off “Complete matches only” to inspect partial criteria.</p> : <div className="table-wrap"><table><thead><tr><th>Stock</th><th>Setup criteria</th><th>Close / RSI</th><th>Volume / RS</th><th>2 ATR stop / 2R target</th></tr></thead><tbody>
          {data.results.map(row => <tr key={row.ticker}><td><Link href={`/stocks/?ticker=${encodeURIComponent(row.ticker)}`}><strong>{row.ticker}</strong></Link><div className="muted">{row.sector}</div></td>
            <td>{row.setups.map(item => <details key={item.id}><summary>{item.matched ? "✓" : "○"} {item.name} · {item.score}% criteria</summary><p className="muted">{item.criteria}</p></details>)}</td>
            <td>${fmt(row.price)}<div className="muted">RSI {fmt(row.rsi)}</div></td><td>{fmt(row.volume_ratio)}×<div className="muted">63-session RS {fmt(row.relative_strength_63d_pp)} pp</div></td>
            <td>${fmt(row.stop_reference)} / ${fmt(row.target_2r)}<div className="muted">Reference entry ${fmt(row.entry_reference)}</div></td></tr>)}
        </tbody></table></div>}
      </section>
      {!!data.unavailable.length && <section className="panel"><h2>Data gaps</h2><p>{data.unavailable.map(row => `${row.ticker}: ${row.status}${row.latest_date ? ` (${row.latest_date})` : ""}`).join(" · ")}</p></section>}
      <section className="panel"><h2>Method</h2>{data.notes.map(note => <p className="muted" key={note}>{note}</p>)}</section>
    </>}
  </>;
}
