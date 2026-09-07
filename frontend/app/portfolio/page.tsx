"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

import styles from "./portfolio.module.css";

type Position = {
  ticker: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  entry_price: number;
  shares: number;
  opened_on: string | null;
  notes: string | null;
  latest_date: string | null;
  current_price: number | null;
  cost_basis: number;
  market_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  target_price: number | null;
  target_upside_pct: number | null;
  stretch_target: number | null;
  stop_loss: number | null;
  stop_distance_pct: number | null;
  nearest_support: number | null;
  support_source: string | null;
  breakout_20d: number | null;
  breakout_50d: number | null;
  breakout_52w: number | null;
  primary_breakout: number | null;
  breakout_status: string;
  reward_risk_ratio: number | null;
  trend: string;
  technical_score: number | null;
  rsi14: number | null;
  atr14: number | null;
  warnings: string[];
};

type Portfolio = {
  position_count: number;
  total_cost_basis: number;
  total_market_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number | null;
  unpriced_positions: number;
  calculated_at: string;
  positions: Position[];
};

type RefreshResponse = {
  refreshed: number;
  failed: number;
  failures: Array<{ ticker: string; error: string }>;
  portfolio: Portfolio;
};

function money(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function pct(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function num(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export default function PortfolioPage() {
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [ticker, setTicker] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [shares, setShares] = useState("");
  const [openedOn, setOpenedOn] = useState("");
  const [notes, setNotes] = useState("");

  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editEntryPrice, setEditEntryPrice] = useState("");
  const [editShares, setEditShares] = useState("");
  const [editOpenedOn, setEditOpenedOn] = useState("");
  const [editNotes, setEditNotes] = useState("");

  async function load() {
    try {
      setError(null);
      setData(await apiGet<Portfolio>("/api/portfolio"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function addPosition(event: FormEvent) {
    event.preventDefault();

    const normalizedTicker = ticker.trim().toUpperCase();
    const entry = Number(entryPrice);
    const qty = Number(shares);

    if (!normalizedTicker || !Number.isFinite(entry) || entry <= 0 || !Number.isFinite(qty) || qty <= 0) {
      setError("Enter a ticker, a positive entry price and a positive number of shares.");
      return;
    }

    setBusy("add");
    setError(null);
    setMessage(null);

    try {
      const result = await apiPost<Portfolio>("/api/portfolio/positions", {
        ticker: normalizedTicker,
        entry_price: entry,
        shares: qty,
        opened_on: openedOn || null,
        notes: notes.trim() || null,
      });

      setData(result);
      setTicker("");
      setEntryPrice("");
      setShares("");
      setOpenedOn("");
      setNotes("");
      setMessage(`${normalizedTicker} added. Yahoo price history was refreshed and technical levels were calculated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function refreshPortfolio() {
    setBusy("refresh");
    setError(null);
    setMessage(null);

    try {
      const result = await apiPost<RefreshResponse>("/api/portfolio/refresh");
      setData(result.portfolio);
      setMessage(
        `Refreshed ${result.refreshed} position${result.refreshed === 1 ? "" : "s"}.` +
          (result.failed ? ` ${result.failed} failed.` : "")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function beginEdit(position: Position) {
    setEditingTicker(position.ticker);
    setEditEntryPrice(String(position.entry_price));
    setEditShares(String(position.shares));
    setEditOpenedOn(position.opened_on || "");
    setEditNotes(position.notes || "");
    setError(null);
    setMessage(null);
  }

  async function saveEdit() {
    if (!editingTicker) return;

    const entry = Number(editEntryPrice);
    const qty = Number(editShares);

    if (!Number.isFinite(entry) || entry <= 0 || !Number.isFinite(qty) || qty <= 0) {
      setError("Entry price and shares must both be positive numbers.");
      return;
    }

    setBusy(`edit-${editingTicker}`);
    setError(null);
    setMessage(null);

    try {
      const result = await apiPut<Portfolio>(`/api/portfolio/positions/${editingTicker}`, {
        entry_price: entry,
        shares: qty,
        opened_on: editOpenedOn || null,
        notes: editNotes.trim() || null,
      });

      setData(result);
      setMessage(`${editingTicker} position updated.`);
      setEditingTicker(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function removePosition(position: Position) {
    if (!window.confirm(`Remove ${position.ticker} from the portfolio tracker?`)) return;

    setBusy(`delete-${position.ticker}`);
    setError(null);
    setMessage(null);

    try {
      await apiDelete(`/api/portfolio/positions/${position.ticker}`);
      await load();
      setMessage(`${position.ticker} removed from the portfolio. Historical market data was kept.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  if (!data) return <Loading />;

  return (
    <>
      <PageHeader
        title="Portfolio Tracker"
        subtitle="Track cost basis, unrealized P/L, technical stops, rule-based targets and breakout levels."
      />

      {error && <ErrorBox message={error} />}

      {message && (
        <div className="job-result SUCCESS">
          <strong>Portfolio updated</strong>
          <span>{message}</span>
        </div>
      )}

      <section className="metric-grid">
        <div className="metric-card">
          <span className="eyebrow">Positions</span>
          <strong>{data.position_count}</strong>
          <span className="muted">tracked holdings</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Cost Basis</span>
          <strong>{money(data.total_cost_basis)}</strong>
          <span className="muted">total capital entered</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Market Value</span>
          <strong>{money(data.total_market_value)}</strong>
          <span className="muted">latest stored close</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Unrealized P/L</span>
          <strong className={data.total_unrealized_pnl >= 0 ? "positive" : "negative"}>
            {money(data.total_unrealized_pnl)}
          </strong>
          <span className={data.total_unrealized_pnl_pct !== null && data.total_unrealized_pnl_pct >= 0 ? "positive" : "negative"}>
            {pct(data.total_unrealized_pnl_pct)}
          </span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Add Holding</span>
            <h2>New Portfolio Position</h2>
          </div>
          <button className="button" onClick={refreshPortfolio} disabled={busy !== null}>
            {busy === "refresh" ? "Refreshing Yahoo…" : "Refresh Prices & Levels"}
          </button>
        </div>

        <form className={styles.form} onSubmit={addPosition}>
          <label>
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="e.g. NVDA"
            />
          </label>

          <label>
            <span>Entry price</span>
            <input
              type="number"
              min="0.0001"
              step="0.0001"
              value={entryPrice}
              onChange={(event) => setEntryPrice(event.target.value)}
              placeholder="150.00"
            />
          </label>

          <label>
            <span>Shares</span>
            <input
              type="number"
              min="0.000001"
              step="0.000001"
              value={shares}
              onChange={(event) => setShares(event.target.value)}
              placeholder="10"
            />
          </label>

          <label>
            <span>Purchase date</span>
            <input
              type="date"
              value={openedOn}
              onChange={(event) => setOpenedOn(event.target.value)}
            />
          </label>

          <label className={styles.notesField}>
            <span>Notes</span>
            <input
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Optional thesis / catalyst"
            />
          </label>

          <button className="button primary" type="submit" disabled={busy !== null}>
            {busy === "add" ? "Adding & analyzing…" : "Add Position"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Holdings</span>
            <h2>Portfolio Monitor</h2>
          </div>
        </div>

        {data.positions.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Entry / Shares</th>
                  <th>Current</th>
                  <th>P/L</th>
                  <th>Target</th>
                  <th>Stop</th>
                  <th>20D Breakout</th>
                  <th>Trend</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((position) => (
                  <tr key={position.ticker}>
                    <td>
                      <Link className="ticker-link" href={`/stocks/?ticker=${encodeURIComponent(position.ticker)}`}>
                        {position.ticker}
                      </Link>
                      <div className="subcell">{position.company_name || ""}</div>
                    </td>
                    <td>
                      <strong>{money(position.entry_price)}</strong>
                      <div className="subcell">{num(position.shares, 4)} shares</div>
                    </td>
                    <td>
                      <strong>{money(position.current_price)}</strong>
                      <div className="subcell">{position.latest_date || "No price"}</div>
                    </td>
                    <td>
                      <strong className={(position.unrealized_pnl || 0) >= 0 ? "positive" : "negative"}>
                        {money(position.unrealized_pnl)}
                      </strong>
                      <div className={(position.unrealized_pnl_pct || 0) >= 0 ? "positive" : "negative"}>
                        {pct(position.unrealized_pnl_pct)}
                      </div>
                    </td>
                    <td>
                      <strong>{money(position.target_price)}</strong>
                      <div className="subcell">{pct(position.target_upside_pct)} · 2R</div>
                    </td>
                    <td>
                      <strong className="negative">{money(position.stop_loss)}</strong>
                      <div className="subcell">{pct(position.stop_distance_pct)}</div>
                    </td>
                    <td>
                      <strong>{money(position.breakout_20d)}</strong>
                      <div className={styles.breakoutStatus}>{position.breakout_status.replaceAll("_", " ")}</div>
                    </td>
                    <td>
                      <span className="signal-pill">{position.trend}</span>
                      <div className="subcell">Score {position.technical_score ?? "—"}</div>
                    </td>
                    <td>
                      <div className={styles.rowActions}>
                        <button className="button" onClick={() => beginEdit(position)} disabled={busy !== null}>
                          Edit
                        </button>
                        <button
                          className={`button ${styles.dangerButton}`}
                          onClick={() => removePosition(position)}
                          disabled={busy !== null}
                        >
                          {busy === `delete-${position.ticker}` ? "Removing…" : "Remove"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState text="No portfolio positions yet. Add your first stock above." />
        )}
      </section>

      {editingTicker && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Edit Holding</span>
              <h2>{editingTicker}</h2>
            </div>
          </div>

          <div className={styles.editGrid}>
            <label>
              <span>Average entry price</span>
              <input type="number" step="0.0001" min="0.0001" value={editEntryPrice} onChange={(e) => setEditEntryPrice(e.target.value)} />
            </label>
            <label>
              <span>Shares</span>
              <input type="number" step="0.000001" min="0.000001" value={editShares} onChange={(e) => setEditShares(e.target.value)} />
            </label>
            <label>
              <span>Purchase date</span>
              <input type="date" value={editOpenedOn} onChange={(e) => setEditOpenedOn(e.target.value)} />
            </label>
            <label>
              <span>Notes</span>
              <input value={editNotes} onChange={(e) => setEditNotes(e.target.value)} />
            </label>
          </div>

          <div className="toolbar">
            <button className="button primary" onClick={saveEdit} disabled={busy !== null}>
              {busy === `edit-${editingTicker}` ? "Saving…" : "Save Changes"}
            </button>
            <button className="button" onClick={() => setEditingTicker(null)} disabled={busy !== null}>
              Cancel
            </button>
          </div>
        </section>
      )}

      {data.positions.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Technical Levels</span>
              <h2>Breakout & Risk Map</h2>
            </div>
          </div>

          <div className={styles.levelGrid}>
            {data.positions.map((position) => (
              <div className={styles.levelCard} key={`levels-${position.ticker}`}>
                <div className="line-between">
                  <div>
                    <Link className="ticker-link" href={`/stocks/?ticker=${encodeURIComponent(position.ticker)}`}>
                      {position.ticker}
                    </Link>
                    <div className="subcell">{position.sector || "Unknown sector"}</div>
                  </div>
                  <span className="score-badge">{position.technical_score ?? "—"}</span>
                </div>

                <div className={styles.levelRows}>
                  <div><span>Current</span><strong>{money(position.current_price)}</strong></div>
                  <div><span>2R target</span><strong className="positive">{money(position.target_price)}</strong></div>
                  <div><span>3R stretch</span><strong>{money(position.stretch_target)}</strong></div>
                  <div><span>Technical stop</span><strong className="negative">{money(position.stop_loss)}</strong></div>
                  <div><span>Nearest support</span><strong>{money(position.nearest_support)}</strong></div>
                  <div><span>Support source</span><strong>{position.support_source || "—"}</strong></div>
                  <div><span>20D breakout</span><strong>{money(position.breakout_20d)}</strong></div>
                  <div><span>50D breakout</span><strong>{money(position.breakout_50d)}</strong></div>
                  <div><span>52W breakout</span><strong>{money(position.breakout_52w)}</strong></div>
                  <div><span>RSI 14</span><strong>{num(position.rsi14)}</strong></div>
                  <div><span>ATR 14</span><strong>{money(position.atr14)}</strong></div>
                  <div><span>Forward R:R</span><strong>{position.reward_risk_ratio === null ? "—" : `${position.reward_risk_ratio.toFixed(2)}R`}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Methodology</span>
            <h2>How the Tracker Calculates Levels</h2>
          </div>
        </div>
        <div className={styles.methodGrid}>
          <div>
            <strong>Target price</strong>
            <p>Uses a transparent 2R target from the latest close. A 3R stretch target is shown separately.</p>
          </div>
          <div>
            <strong>Stop loss</strong>
            <p>Uses the nearest valid SMA20, SMA50, 20-day low or 50-day low with an ATR buffer, while keeping at least 1.5 ATR of room.</p>
          </div>
          <div>
            <strong>Breakout levels</strong>
            <p>Uses the prior 20-day high as the primary breakout, plus the prior 50-day and 52-week highs for larger resistance levels.</p>
          </div>
        </div>
        <p className={styles.disclaimer}>
          These are rules-based planning levels generated from market data. They are not guaranteed outcomes or personalized financial advice; earnings gaps and overnight moves can pass through stop prices.
        </p>
      </section>
    </>
  );
}
