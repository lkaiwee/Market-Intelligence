"use client";

import { useEffect, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import type { EarningsEvent } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

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

export default function EarningsPage() {
  const [data, setData] = useState<Upcoming | null>(null);
  const [refreshResult, setRefreshResult] = useState<RefreshResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function load() {
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

  async function refreshCalendar() {
    setRunning(true);
    setRefreshResult(null);

    try {
      const result = await apiPost<RefreshResult>(
        "/api/earnings/refresh?horizon=3month"
      );

      setRefreshResult(result);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error && !data) {
    return (
      <>
        <PageHeader
          title="Earnings Calendar"
          subtitle="Upcoming blue-chip earnings and market-impact mapping."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!data) return <Loading />;

  return (
    <>
      <PageHeader
        title="Earnings Calendar"
        subtitle="Upcoming blue-chip earnings from Yahoo Finance with peer-impact mapping."
      />

      <div className="toolbar">
        <button
          className="button primary"
          onClick={refreshCalendar}
          disabled={running}
        >
          {running ? "Fetching Yahoo Earnings…" : "Refresh Upcoming Earnings"}
        </button>

        <button
          className="button"
          onClick={load}
          disabled={running}
        >
          Refresh view
        </button>

        <span className="muted">
          Automatic calendar update: Sunday 18:00 SGT
        </span>
      </div>

      {running && (
        <div className="job-result PARTIAL">
          <strong>Refreshing the 90-day earnings calendar</strong>
          <span>
            Yahoo Finance is being queried and the results are filtered to your
            blue-chip universe.
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
            Earnings refresh: {refreshResult.stored_blue_chip_events} blue-chip events stored
          </strong>

          <span>
            Yahoo returned {refreshResult.received_market_events} market events
            {refreshResult.unique_market_symbols !== undefined
              ? ` across ${refreshResult.unique_market_symbols} symbols`
              : ""}
            .
          </span>

          {refreshResult.diagnostic && (
            <span>{refreshResult.diagnostic}</span>
          )}
        </div>
      )}

      {error && <ErrorBox message={error} />}

      <section className="metric-grid">
        <div className="metric-card">
          <span className="eyebrow">Window</span>
          <strong>{data.start_date}</strong>
          <span className="muted">through {data.end_date}</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Events</span>
          <strong>{data.total_events}</strong>
          <span className="muted">blue-chip earnings</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">High Impact</span>
          <strong>
            {data.events.filter((event) => event.impact_score >= 9).length}
          </strong>
          <span className="muted">impact score ≥ 9</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Data Source</span>
          <strong>Yahoo</strong>
          <span className="muted">90-day earnings calendar</span>
        </div>
      </section>

      <section className="panel">
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
                <span className="muted">{event.sector}</span>

                <div className="detail-grid">
                  <div>
                    <span>EPS Estimate</span>
                    <strong>
                      {event.eps_estimate !== null
                        ? `${event.currency || ""} ${event.eps_estimate}`
                        : "—"}
                    </strong>
                  </div>

                  <div>
                    <span>Impact</span>
                    <strong>{event.impact_level}</strong>
                  </div>
                </div>

                <p>{event.impact_note}</p>

                {event.related_tickers.length > 0 && (
                  <div>
                    <span className="eyebrow">Related</span>

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
  );
}
