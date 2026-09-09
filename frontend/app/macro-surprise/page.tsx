"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

type Release = {
  id: number; indicator: string; release_at: string; period: string; unit: string;
  actual: number | null; consensus: number | null; previous: number | null;
  actual_source: string | null; consensus_source: string | null; notes: string | null;
  status: string; surprise: number | null; surprise_pct: number | null;
  standardized_surprise: number | null; history_count: number;
};
type Dashboard = { count: number; releases: Release[]; methodology: Record<string, string> };
type Draft = {
  indicator: string; release_at: string; period: string; unit: string;
  actual: string; consensus: string; previous: string; actual_source: string;
  consensus_source: string; notes: string;
};
const fmt = (value: number | null, suffix = "") => value === null ? "—" : `${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}${suffix}`;
function localDate(value: string) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
const blank = (): Draft => ({ indicator: "", release_at: "", period: "", unit: "", actual: "", consensus: "", previous: "", actual_source: "", consensus_source: "", notes: "" });

export default function MacroSurprisePage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [draft, setDraft] = useState<Draft>(() => blank());
  const [editing, setEditing] = useState<number | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiGet<Dashboard>("/api/macro-surprise").then(result => { if (active) setData(result); }).catch(err => { if (active) setError(String(err)); });
    return () => { active = false; };
  }, []);

  function field(name: keyof Draft, value: string) { setDraft(current => ({ ...current, [name]: value })); }
  function edit(row: Release) {
    setEditing(row.id);
    setDraft({ indicator: row.indicator, release_at: localDate(row.release_at), period: row.period, unit: row.unit,
      actual: row.actual === null ? "" : String(row.actual), consensus: row.consensus === null ? "" : String(row.consensus),
      previous: row.previous === null ? "" : String(row.previous), actual_source: row.actual_source || "",
      consensus_source: row.consensus_source || "", notes: row.notes || "" });
    setMessage(null);
    document.getElementById("release-form")?.scrollIntoView({ behavior: "smooth" });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setMessage(null);
    try {
      const payload = { ...draft, release_at: new Date(draft.release_at).toISOString(),
        actual: draft.actual === "" ? null : draft.actual, consensus: draft.consensus === "" ? null : draft.consensus,
        previous: draft.previous === "" ? null : draft.previous, actual_source: draft.actual_source || null,
        consensus_source: draft.consensus_source || null, notes: draft.notes || null };
      const result = editing === null
        ? await apiPost<Dashboard>("/api/macro-surprise", payload)
        : await apiPut<Dashboard>(`/api/macro-surprise/${editing}`, payload);
      setData(result); setEditing(null); setDraft(blank()); setMessage("Release saved. Surprise calculations have been updated.");
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }
  async function remove(row: Release) {
    if (!window.confirm(`Delete the ${row.indicator} release for ${row.period}?`)) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      setData(await apiDelete<Dashboard>(`/api/macro-surprise/${row.id}`));
      if (editing === row.id) { setEditing(null); setDraft(blank()); }
      setMessage("Release deleted.");
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }
  const releases = data?.releases.filter(row => `${row.indicator} ${row.period} ${row.unit}`.toLowerCase().includes(filter.toLowerCase())) || [];
  return <div className="macro-surprise-page">
    <PageHeader title="Macro Surprise Engine" subtitle="7.6 · Compare published actuals with attributable consensus forecasts and prior releases." />
    {error && <ErrorBox message={error} />}
    {message && <p role="status" className="notice">{message}</p>}
    <section className="panel">
      <div className="panel-heading"><h2>Actuals versus expectations</h2><span className="eyebrow">Recorded sources</span></div>
      <p className="muted">Enter actuals from the published release and consensus from your forecast source. The free setup has no automatic consensus feed. Leave unknown values blank; zero is a real observation. Use separate series and units for monthly, annual, headline and core readings.</p>
      {data && <div className="macro-metrics">
        <div><span>Recorded releases</span><strong>{data.count}</strong></div>
        <div><span>Comparable releases</span><strong>{data.releases.filter(row => row.status === "complete").length}</strong></div>
        <div><span>Awaiting actuals</span><strong>{data.releases.filter(row => row.status === "scheduled" || row.status === "awaiting_actual").length}</strong></div>
      </div>}
    </section>
    <section className="panel" id="release-form">
      <div className="panel-heading"><h2>{editing === null ? "Record a release" : "Edit release"}</h2></div>
      <form onSubmit={save}>
        <div className="macro-form">
          <label>Indicator / series<input required maxLength={120} placeholder="e.g. US headline CPI, month on month" value={draft.indicator} onChange={e => field("indicator", e.target.value)} /></label>
          <label>Release time (your local time)<input type="datetime-local" required value={draft.release_at} onChange={e => field("release_at", e.target.value)} /></label>
          <label>Reporting period<input required maxLength={80} placeholder="e.g. August 2026" value={draft.period} onChange={e => field("period", e.target.value)} /></label>
          <label>Unit / scale<input required maxLength={80} placeholder="e.g. % m/m, thousands, index points" value={draft.unit} onChange={e => field("unit", e.target.value)} /></label>
          {(["actual", "consensus", "previous"] as const).map(name => <label key={name}>{name === "previous" ? "Previous reported value (optional)" : name === "actual" ? "Published actual" : "Consensus forecast"}<input type="number" step="any" value={draft[name]} onChange={e => field(name, e.target.value)} /></label>)}
          <label>Actual source (required with actual)<input required={draft.actual !== ""} maxLength={500} placeholder="Agency release URL or publication citation" value={draft.actual_source} onChange={e => field("actual_source", e.target.value)} /></label>
          <label>Consensus source (required with forecast)<input required={draft.consensus !== ""} maxLength={500} placeholder="Publication / survey and forecast date" value={draft.consensus_source} onChange={e => field("consensus_source", e.target.value)} /></label>
          <label className="wide">Notes / revisions<textarea maxLength={2000} value={draft.notes} onChange={e => field("notes", e.target.value)} placeholder="Record whether actuals or the previous reading were revised." /></label>
        </div>
        <div className="actions"><button className="button primary" type="submit" disabled={busy}>{busy ? "Saving…" : editing === null ? "Save release" : "Save changes"}</button>{editing !== null && <button className="button" type="button" disabled={busy} onClick={() => { setEditing(null); setDraft(blank()); }}>Cancel edit</button>}</div>
      </form>
    </section>
    <section className="panel">
      <div className="panel-heading"><h2>Release history</h2><label className="search">Filter releases<input aria-label="Filter releases" value={filter} onChange={e => setFilter(e.target.value)} placeholder="Indicator, period or unit" /></label></div>
      {!data && !error && <Loading />}
      {data && releases.length === 0 && <EmptyState text={data.count ? "No releases match your filter." : "No releases recorded yet. Add a sourced forecast or published release above."} />}
      {releases.length > 0 && <div className="table-wrap"><table><thead><tr><th>Release / reporting period</th><th>Actual</th><th>Consensus</th><th>Previous</th><th>Surprise</th><th>Relative surprise</th><th>Standardized</th><th>Sources / actions</th></tr></thead><tbody>{releases.map(row => <tr key={row.id}>
        <td><strong>{row.indicator}</strong><small>{row.period} · {row.unit}</small><small>{new Date(row.release_at).toLocaleString()}</small><small>{row.status.replaceAll("_", " ")}</small></td>
        <td>{fmt(row.actual)}</td><td>{fmt(row.consensus)}</td><td>{fmt(row.previous)}</td>
        <td>{fmt(row.surprise)}<small>{row.surprise === null ? "Needs actual + consensus" : row.surprise > 0 ? "Above consensus" : row.surprise < 0 ? "Below consensus" : "In line"}</small></td>
        <td>{fmt(row.surprise_pct, "%")}{row.consensus === 0 && <small>Zero consensus</small>}</td>
        <td>{fmt(row.standardized_surprise, " σ")}<small>{row.history_count} prior comparable releases</small></td>
        <td className="sources"><details><summary>View sources</summary><p>Actual: {row.actual_source || "Not recorded"}</p><p>Consensus: {row.consensus_source || "Not recorded"}</p>{row.notes && <p>{row.notes}</p>}</details><div className="actions"><button className="button" disabled={busy} onClick={() => edit(row)}>Edit</button><button className="button" disabled={busy} onClick={() => remove(row)}>Delete</button></div></td>
      </tr>)}</tbody></table></div>}
    </section>
    {data && <section className="panel"><div className="panel-heading"><h2>How surprises are calculated</h2></div><p className="muted">{data.methodology.difference}</p><p className="muted">{data.methodology.percent}</p><p className="muted">{data.methodology.standardization}</p><p className="muted">{data.methodology.history_note}</p><a className="reference" href={data.methodology.reference_url} target="_blank" rel="noreferrer">Federal Reserve: macroeconomic surprise methodology ↗</a></section>}
    <style jsx>{`
      .macro-surprise-page .panel { margin-bottom: 18px; }
      .muted, small { color: var(--muted); line-height: 1.6; }
      small { display: block; font-size: 11px; margin-top: 5px; }
      .macro-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
      label { display: grid; gap: 7px; color: var(--muted); font-size: 12px; }
      input, textarea { width: 100%; padding: 10px; background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: 7px; min-width: 0; }
      textarea { font: inherit; min-height: 70px; resize: vertical; }
      .wide { grid-column: 1 / -1; }
      .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
      .macro-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 22px; }
      .macro-metrics span, .macro-metrics strong { display: block; }
      .macro-metrics span { font-size: 12px; color: var(--muted); }
      .macro-metrics strong { font-size: 28px; margin-top: 6px; }
      .sources { min-width: 220px; max-width: 360px; overflow-wrap: anywhere; white-space: normal; }
      .sources p { font-size: 12px; line-height: 1.5; }
      summary { cursor: pointer; color: var(--blue); }
      .search { max-width: 300px; }
      .notice, .reference { color: var(--accent); }
      @media (max-width: 700px) { .macro-form { grid-template-columns: 1fr; } .macro-metrics { grid-template-columns: 1fr; } .panel-heading { flex-wrap: wrap; } }
    `}</style>
  </div>;
}
