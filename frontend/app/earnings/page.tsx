"use client";

import { useEffect, useMemo, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import type { EarningsEvent } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import styles from "./earnings.module.css";

type Upcoming = {
  start_date: string;
  end_date: string;
  total_events: number;
  events: EarningsEvent[];
};

type RefreshResult = {
  horizon: string;
  received_market_events: number;
  stored_blue_chip_events: number;
  refreshed_at: string;
  unique_market_symbols?: number;
  matched_blue_chip_symbols?: string[];
  returned_symbol_sample?: string[];
  diagnostic?: string | null;
};

type MacroScenario = {
  upside: string;
  base: string;
  downside: string;
};

type MacroEvent = {
  event_type: string;
  title: string;
  release_date: string;
  release_at_et: string;
  release_at_sgt: string;
  source: string;
  source_url: string;
  impact_score: number;
  note: string;
  prediction: "BULLISH" | "HAWKISH" | "BEARISH" | "UNAVAILABLE";
  equity_bias: string;
  policy_bias: string;
  confidence: number | null;
  rationale: string;
  scenarios: MacroScenario;
};

type MacroData = {
  generated_at: string;
  start_date: string;
  end_date: string;
  timezone_note: string;
  regime: {
    label: string;
    market_bias: string;
    inflation_state: string;
    labor_state: string;
    explanation: string;
  };
  latest_data: {
    headline_cpi_yoy: number | null;
    headline_cpi_period: string | null;
    core_cpi_yoy: number | null;
    core_cpi_period: string | null;
    unemployment_rate: number | null;
    unemployment_period: string | null;
    payroll_change_k: number | null;
    payroll_period: string | null;
  };
  events: MacroEvent[];
  warnings: string[];
  sources: {
    name: string;
    url: string;
    covers: string;
  }[];
  methodology: string;
};

function formatDateTime(value: string, zone: "ET" | "SGT") {
  const date = new Date(value);

  return new Intl.DateTimeFormat("en-SG", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone:
      zone === "ET"
        ? "America/New_York"
        : "Asia/Singapore",
  }).format(date);
}

function valueOrDash(
  value: number | null,
  suffix = "",
  digits = 1,
) {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export default function EarningsPage() {
  const [data, setData] = useState<Upcoming | null>(null);
  const [macro, setMacro] = useState<MacroData | null>(null);
  const [refreshResult, setRefreshResult] =
    useState<RefreshResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [macroError, setMacroError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [macroRunning, setMacroRunning] = useState(false);

  async function loadEarnings() {
    try {
      setError(null);

      setData(
        await apiGet<Upcoming>(
          "/api/earnings/upcoming?days=90&min_impact=0"
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function loadMacro(force = false) {
    setMacroRunning(true);

    try {
      setMacroError(null);

      setMacro(
        await apiGet<MacroData>(
          `/api/earnings/macro?days=120&refresh=${
            force ? "true" : "false"
          }`
        )
      );
    } catch (err) {
      setMacroError(
        err instanceof Error ? err.message : String(err)
      );
    } finally {
      setMacroRunning(false);
    }
  }

  async function refreshCalendar() {
    setRunning(true);
    setRefreshResult(null);

    try {
      const result = await apiPost<RefreshResult>(
        "/api/earnings/refresh?horizon=3month"
      );

      setRefreshResult(result);
      await loadEarnings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    loadEarnings();
    loadMacro(false);
  }, []);

  const nextHighImpactMacro = useMemo(() => {
    return macro?.events.find(
      (event) => event.impact_score >= 9 && new Date(event.release_at_et).getTime() >= Date.now()
    );
  }, [macro]);

  if (!data && !macro && !error && !macroError) {
    return <Loading />;
  }

  return (
    <>
      <PageHeader
        title="Earnings & U.S. Macro Calendar"
        subtitle="Company earnings plus the U.S. inflation, jobs and Federal Reserve releases most likely to move the market."
      />

      <div className="toolbar">
        <button
          className="button primary"
          onClick={refreshCalendar}
          disabled={running || macroRunning}
        >
          {running
            ? "Fetching Yahoo Earnings…"
            : "Refresh Upcoming Earnings"}
        </button>

        <button
          className="button"
          onClick={() => loadMacro(true)}
          disabled={running || macroRunning}
        >
          {macroRunning
            ? "Refreshing U.S. Macro…"
            : "Refresh U.S. Macro"}
        </button>

        <span className="muted">
          Earnings auto-update: Sunday 18:00 SGT
        </span>
      </div>

      {running && (
        <div className="job-result PARTIAL">
          <strong>Refreshing the 90-day earnings calendar</strong>
          <span>
            Yahoo Finance is being queried and filtered to your
            screening universe.
          </span>
        </div>
      )}

      {refreshResult && (
        <div
          className={`job-result ${
            refreshResult.stored_blue_chip_events > 0
              ? "SUCCESS"
              : "PARTIAL"
          }`}
        >
          <strong>
            Earnings refresh:{" "}
            {refreshResult.stored_blue_chip_events} events stored
          </strong>

          {refreshResult.diagnostic && (
            <span>{refreshResult.diagnostic}</span>
          )}
        </div>
      )}

      {error && <ErrorBox message={error} />}
      {macroError && <ErrorBox message={macroError} />}
      {macroRunning && !macro && <p className="muted">Loading official U.S. macro data…</p>}

      {macro && (
        <>
          <section className="metric-grid">
            <div className="metric-card">
              <span className="eyebrow">Macro Regime</span>
              <strong>{macro.regime.label}</strong>
              <span className="muted">
                {macro.regime.market_bias} bias
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">Headline CPI YoY</span>
              <strong>
                {valueOrDash(
                  macro.latest_data.headline_cpi_yoy,
                  "%",
                  1
                )}
              </strong>
              <span className="muted">
                BLS reference month: {macro.latest_data.headline_cpi_period?.slice(0, 7) || "unavailable"}
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">Core CPI YoY</span>
              <strong>
                {valueOrDash(
                  macro.latest_data.core_cpi_yoy,
                  "%",
                  1
                )}
              </strong>
              <span className="muted">
                BLS reference month: {macro.latest_data.core_cpi_period?.slice(0, 7) || "unavailable"}
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">Latest Payroll Change</span>
              <strong>
                {macro.latest_data.payroll_change_k !== null
                  ? `${macro.latest_data.payroll_change_k.toFixed(
                      0
                    )}K`
                  : "—"}
              </strong>
              <span className="muted">
                unemployment{" "}
                {valueOrDash(
                  macro.latest_data.unemployment_rate,
                  "%",
                  1
                )}
                {" · "}{macro.latest_data.payroll_period?.slice(0, 7) || "reference month unavailable"}
              </span>
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  U.S. Market-Moving Releases
                </span>
                <h2>Macro Risk Calendar</h2>
              </div>

              {nextHighImpactMacro && (
                <div className={styles.nextEvent}>
                  <span>Next major event</span>
                  <strong>{nextHighImpactMacro.title}</strong>
                  <small>
                    {formatDateTime(
                      nextHighImpactMacro.release_at_sgt,
                      "SGT"
                    )}{" "}
                    SGT
                  </small>
                </div>
              )}
            </div>

            <div className={styles.regimeBanner}>
              <div>
                <span className="eyebrow">
                  Current Model Bias
                </span>
                <strong
                  className={
                    styles[
                      `bias${macro.regime.market_bias}`
                    ] || ""
                  }
                >
                  {macro.regime.market_bias}
                </strong>
              </div>

              <p>{macro.regime.explanation}</p>
            </div>

            <p className={`muted ${styles.methodology}`}>
              {macro.methodology}
            </p>

            {macro.warnings.length > 0 && (
              <div className="job-result PARTIAL">
                <strong>Macro data-source note</strong>
                {macro.warnings.map((warning) => (
                  <span key={warning}>{warning}</span>
                ))}
              </div>
            )}

            {macro.events.length ? (
              <div className={styles.macroGrid}>
                {macro.events.map((event) => (
                  <article
                    className={styles.macroCard}
                    key={`${event.event_type}-${event.release_at_et}`}
                  >
                    <div className="line-between">
                      <div>
                        <span className="eyebrow">
                          {event.event_type}
                        </span>
                        <h3>{event.title}</h3>
                      </div>

                      <span className="impact-badge large">
                        {event.impact_score}/10
                      </span>
                    </div>

                    <div className={styles.timeGrid}>
                      <div>
                        <span>U.S. Eastern</span>
                        <strong>
                          {formatDateTime(
                            event.release_at_et,
                            "ET"
                          )}{" "}
                          ET
                        </strong>
                      </div>

                      <div>
                        <span>Singapore</span>
                        <strong>
                          {formatDateTime(
                            event.release_at_sgt,
                            "SGT"
                          )}{" "}
                          SGT
                        </strong>
                      </div>
                    </div>

                    <div className={styles.biasRow}>
                      <span
                        className={`${styles.biasBadge} ${
                          styles[
                            `bias${event.prediction}`
                          ] || ""
                        }`}
                      >
                        Model bias: {event.prediction}
                      </span>

                      <span className={styles.policyBadge}>
                        Fed: {event.policy_bias}
                      </span>

                      <span className={styles.confidence}>
                        {event.confidence === null ? "Score unavailable" : `Rule score ${event.confidence}/100`}
                      </span>
                    </div>

                    <p className={styles.rationale}>
                      {event.rationale}
                    </p>

                    <details className={styles.scenarios}>
                      <summary>
                        Expected market-reaction scenarios
                      </summary>

                      <div>
                        <span>Hot / strong surprise</span>
                        <p>{event.scenarios.upside}</p>
                      </div>

                      <div>
                        <span>Near expectations</span>
                        <p>{event.scenarios.base}</p>
                      </div>

                      <div>
                        <span>Cool / weak surprise</span>
                        <p>{event.scenarios.downside}</p>
                      </div>
                    </details>

                    <div className={styles.sourceLine}>
                      <span className="muted">
                        Source: {event.source}
                      </span>

                      <a
                        href={event.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Official schedule ↗
                      </a>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState text="No U.S. macro releases were found in the selected window." />
            )}
          </section>
        </>
      )}

      {data && (
        <>
          <section className="metric-grid">
            <div className="metric-card">
              <span className="eyebrow">Earnings Window</span>
              <strong>{data.start_date}</strong>
              <span className="muted">
                through {data.end_date}
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">Earnings Events</span>
              <strong>{data.total_events}</strong>
              <span className="muted">
                monitored companies
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">High Impact</span>
              <strong>
                {
                  data.events.filter(
                    (event) => event.impact_score >= 9
                  ).length
                }
              </strong>
              <span className="muted">
                impact score ≥ 9
              </span>
            </div>

            <div className="metric-card">
              <span className="eyebrow">Earnings Source</span>
              <strong>Yahoo</strong>
              <span className="muted">
                ticker-level calendars
              </span>
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  Company Catalysts
                </span>
                <h2>Upcoming Earnings</h2>
              </div>
            </div>

            {data.events.length ? (
              <div className="earnings-grid">
                {data.events.map((event) => (
                  <div
                    className="earnings-card"
                    key={`${event.ticker}-${event.report_date}`}
                  >
                    <div className="line-between">
                      <div>
                        <span className="eyebrow">
                          {event.report_date}
                        </span>
                        <h3>{event.ticker}</h3>
                      </div>

                      <span className="impact-badge large">
                        {event.impact_score}/10
                      </span>
                    </div>

                    <strong>{event.company_name}</strong>
                    <span className="muted">
                      {event.sector}
                    </span>

                    <div className="detail-grid">
                      <div>
                        <span>EPS Estimate</span>
                        <strong>
                          {event.eps_estimate !== null
                            ? `${event.currency || ""} ${
                                event.eps_estimate
                              }`
                            : "—"}
                        </strong>
                      </div>

                      <div>
                        <span>Impact</span>
                        <strong>
                          {event.impact_level}
                        </strong>
                      </div>
                    </div>

                    <p>{event.impact_note}</p>

                    {event.related_tickers.length > 0 && (
                      <div>
                        <span className="eyebrow">
                          Related
                        </span>

                        <div className="ticker-chip-row">
                          {event.related_tickers
                            .slice(0, 8)
                            .map((ticker) => (
                              <span
                                className="ticker-chip"
                                key={ticker}
                              >
                                {ticker}
                              </span>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text="No upcoming earnings are stored yet. Click Refresh Upcoming Earnings to populate the 90-day Yahoo calendar." />
            )}
          </section>
        </>
      )}
    </>
  );
}
