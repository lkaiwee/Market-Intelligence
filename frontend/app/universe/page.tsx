"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import styles from "./universe.module.css";

type UniverseStock = {
  ticker: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  screening_enabled: boolean;
  earnings_enabled: boolean;
  earnings_impact_score: number;
  is_core: boolean;
};

type UniverseResponse = {
  count: number;
  stocks: UniverseStock[];
};

type JobResult = {
  job_name?: string;
  status?: string;
  detail?: string;
  stored_blue_chip_events?: number;
  diagnostic?: string | null;
};

export default function UniversePage() {
  const [allStocks, setAllStocks] = useState<UniverseStock[] | null>(null);
  const [customStocks, setCustomStocks] = useState<UniverseStock[]>([]);
  const [ticker, setTicker] = useState("");
  const [screening, setScreening] = useState(true);
  const [earnings, setEarnings] = useState(true);
  const [impact, setImpact] = useState(7);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);

      const [all, custom] = await Promise.all([
        apiGet<UniverseResponse>("/api/universe/stocks?include_core=true"),
        apiGet<UniverseResponse>("/api/universe/stocks?include_core=false"),
      ]);

      setAllStocks(all.stocks);
      setCustomStocks(custom.stocks);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function addStock(event: FormEvent) {
    event.preventDefault();

    const normalized = ticker.trim().toUpperCase();
    if (!normalized) return;

    setBusy("add");
    setError(null);
    setMessage(null);

    try {
      const result = await apiPost<{ message: string }>(
        "/api/universe/stocks",
        {
          ticker: normalized,
          screening_enabled: screening,
          earnings_enabled: earnings,
          earnings_impact_score: impact,
        }
      );

      setMessage(
        `${result.message} Run the relevant refresh below to populate its data now.`
      );
      setTicker("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function saveStock(stock: UniverseStock) {
    setBusy(`save-${stock.ticker}`);
    setError(null);
    setMessage(null);

    try {
      await apiPut(`/api/universe/stocks/${stock.ticker}`, {
        screening_enabled: stock.screening_enabled,
        earnings_enabled: stock.earnings_enabled,
        earnings_impact_score: stock.earnings_impact_score,
      });

      setMessage(`${stock.ticker} settings updated.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function removeStock(stock: UniverseStock) {
    if (!window.confirm(`Remove ${stock.ticker} from the custom universe?`)) {
      return;
    }

    setBusy(`delete-${stock.ticker}`);
    setError(null);
    setMessage(null);

    try {
      await apiDelete(`/api/universe/stocks/${stock.ticker}`);
      setMessage(`${stock.ticker} removed from the custom universe.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function runScreener() {
    setBusy("screener");
    setError(null);
    setMessage(null);

    try {
      const result = await apiPost<JobResult>(
        "/api/jobs/screener/run?force_fundamentals=false"
      );

      setMessage(
        result.detail ||
          "Screener update completed. Open Screener to view the new ranking."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function runEarnings() {
    setBusy("earnings");
    setError(null);
    setMessage(null);

    try {
      const result = await apiPost<JobResult>(
        "/api/earnings/refresh?horizon=3month"
      );

      setMessage(
        `Earnings refresh completed. ${
          result.stored_blue_chip_events ?? 0
        } upcoming events stored. ${result.diagnostic || ""}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function updateLocal(
    ticker: string,
    updates: Partial<UniverseStock>
  ) {
    setCustomStocks((stocks) =>
      stocks.map((stock) =>
        stock.ticker === ticker
          ? { ...stock, ...updates }
          : stock
      )
    );
  }

  if (!allStocks) return <Loading />;

  const coreCount = allStocks.filter((stock) => stock.is_core).length;

  return (
    <>
      <PageHeader
        title="Stock Universe"
        subtitle="Add stocks to the daily investment screener, earnings monitoring, or both."
      />

      {error && <ErrorBox message={error} />}

      {message && (
        <div className="job-result SUCCESS">
          <strong>Universe updated</strong>
          <span>{message}</span>
        </div>
      )}

      <section className="metric-grid">
        <div className="metric-card">
          <span className="eyebrow">Built-In</span>
          <strong>{coreCount}</strong>
          <span className="muted">core blue-chip stocks</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Custom</span>
          <strong>{customStocks.length}</strong>
          <span className="muted">stocks you added</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Screening</span>
          <strong>
            {allStocks.filter((stock) => stock.screening_enabled).length}
          </strong>
          <span className="muted">enabled stocks</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Earnings</span>
          <strong>
            {allStocks.filter((stock) => stock.earnings_enabled).length}
          </strong>
          <span className="muted">monitored stocks</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Add Stock</span>
            <h2>Expand Your Universe</h2>
          </div>
        </div>

        <form className={styles.form} onSubmit={addStock}>
          <label>
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="e.g. SNDK"
              autoCapitalize="characters"
            />
          </label>

          <label>
            <span>Earnings impact</span>
            <select
              value={impact}
              onChange={(event) => setImpact(Number(event.target.value))}
            >
              {[10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((value) => (
                <option value={value} key={value}>
                  {value}/10
                </option>
              ))}
            </select>
          </label>

          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={screening}
              onChange={(event) => setScreening(event.target.checked)}
            />
            <span>Daily screening</span>
          </label>

          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={earnings}
              onChange={(event) => setEarnings(event.target.checked)}
            />
            <span>Earnings monitoring</span>
          </label>

          <button
            className="button primary"
            type="submit"
            disabled={busy !== null}
          >
            {busy === "add" ? "Validating Yahoo…" : "Add Stock"}
          </button>
        </form>

        <p className={`muted ${styles.note}`}>
          Yahoo Finance is used to validate the ticker and automatically fill
          company name, sector and industry.
        </p>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Refresh Data</span>
            <h2>Run Updates Now</h2>
          </div>
        </div>

        <div className="toolbar">
          <button
            className="button primary"
            onClick={runScreener}
            disabled={busy !== null}
          >
            {busy === "screener"
              ? "Updating Screener…"
              : "Update Screener Now"}
          </button>

          <button
            className="button"
            onClick={runEarnings}
            disabled={busy !== null}
          >
            {busy === "earnings"
              ? "Refreshing Earnings…"
              : "Refresh Earnings Now"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Custom Stocks</span>
            <h2>Your Added Stocks</h2>
          </div>
        </div>

        {customStocks.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Company</th>
                  <th>Sector</th>
                  <th>Screening</th>
                  <th>Earnings</th>
                  <th>Impact</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {customStocks.map((stock) => (
                  <tr key={stock.ticker}>
                    <td>
                      <strong className="ticker-link">
                        {stock.ticker}
                      </strong>
                    </td>

                    <td>
                      {stock.company_name || "—"}
                      <div className="subcell">
                        {stock.industry || ""}
                      </div>
                    </td>

                    <td>{stock.sector || "—"}</td>

                    <td>
                      <input
                        type="checkbox"
                        checked={stock.screening_enabled}
                        onChange={(event) =>
                          updateLocal(stock.ticker, {
                            screening_enabled: event.target.checked,
                          })
                        }
                      />
                    </td>

                    <td>
                      <input
                        type="checkbox"
                        checked={stock.earnings_enabled}
                        onChange={(event) =>
                          updateLocal(stock.ticker, {
                            earnings_enabled: event.target.checked,
                          })
                        }
                      />
                    </td>

                    <td>
                      <select
                        value={stock.earnings_impact_score}
                        onChange={(event) =>
                          updateLocal(stock.ticker, {
                            earnings_impact_score: Number(event.target.value),
                          })
                        }
                      >
                        {[10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((value) => (
                          <option value={value} key={value}>
                            {value}
                          </option>
                        ))}
                      </select>
                    </td>

                    <td>
                      <div className={`toolbar ${styles.compactToolbar}`}>
                        <button
                          className="button"
                          onClick={() => saveStock(stock)}
                          disabled={busy !== null}
                        >
                          {busy === `save-${stock.ticker}`
                            ? "Saving…"
                            : "Save"}
                        </button>

                        <button
                          className={`button ${styles.dangerButton}`}
                          onClick={() => removeStock(stock)}
                          disabled={busy !== null}
                        >
                          {busy === `delete-${stock.ticker}`
                            ? "Removing…"
                            : "Remove"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState text="You have not added any custom stocks yet." />
        )}
      </section>
    </>
  );
}
