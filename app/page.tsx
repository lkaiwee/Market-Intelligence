"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

function pct(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);
      setData(await apiGet<Dashboard>("/api/dashboard"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, []);

  if (error) {
    return (
      <>
        <PageHeader
          title="Market Dashboard"
          subtitle="Unified view of market regime, opportunities, alerts and earnings."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!data) return <Loading />;

  return (
    <>
      <PageHeader
        title="Market Dashboard"
        subtitle="Unified view of market regime, opportunities, alerts and earnings."
      />

      <section className="metric-grid">
        <div className="metric-card">
          <span className="eyebrow">Market Regime</span>
          <strong className={`regime ${data.market_regime || "NEUTRAL"}`}>
            {data.market_regime || "NO DATA"}
          </strong>
          <span className="muted">Cross-sector risk positioning</span>
        </div>

        <div className="metric-card score-card">
          <ScoreRing score={data.risk_on_score} label="Risk-On Score" />
        </div>

        <div className="metric-card">
          <span className="eyebrow">Rotation Leaders</span>
          <div className="ticker-chip-row">
            {data.strongest_rotation.length ? (
              data.strongest_rotation.map((ticker) => (
                <span className="ticker-chip" key={ticker}>
                  {ticker}
                </span>
              ))
            ) : (
              <span className="muted">No rotation data</span>
            )}
          </div>
          <span className="muted">Relative leadership vs SPY</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Scheduler</span>
          <strong>
            {data.scheduler.scheduler_running ? "RUNNING" : "STOPPED"}
          </strong>
          <span className="muted">
            Daily {data.scheduler.daily_schedule} · {data.scheduler.timezone}
          </span>
        </div>
      </section>

      <section className="two-column">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Top Opportunities</span>
              <h2>Investment Screener</h2>
            </div>
            <Link href="/screener" className="text-link">
              View all →
            </Link>
          </div>

          {data.top_investment_opportunities.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Score</th>
                    <th>Price</th>
                    <th>Pullback</th>
                    <th>Trend</th>
                    <th>Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_investment_opportunities.map((item) => (
                    <tr key={item.ticker}>
                      <td>
                        <Link
                          className="ticker-link"
                          href={`/stocks/${item.ticker}`}
                        >
                          {item.ticker}
                        </Link>
                      </td>
                      <td>
                        <span className="score-badge">
                          {item.opportunity_score}
                        </span>
                      </td>
                      <td>${fmt(item.price)}</td>
                      <td className={item.pullback_pct < 0 ? "negative" : "positive"}>
                        {pct(item.pullback_pct)}
                      </td>
                      <td>{item.trend}</td>
                      <td>
                        <span className="signal-pill">
                          {item.investment_signal}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState text="No investment analyses are available yet. Refresh fundamentals for watchlist stocks to populate this section." />
          )}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Latest Alerts</span>
              <h2>Signal Feed</h2>
            </div>
            <Link href="/alerts" className="text-link">
              View all →
            </Link>
          </div>

          {data.alerts.length ? (
            <div className="alert-list compact">
              {data.alerts.slice(0, 6).map((alert) => (
                <div className="alert-row" key={alert.id}>
                  <div>
                    <div className="alert-title-line">
                      <span className={`severity ${alert.severity}`}>
                        {alert.severity}
                      </span>
                      <strong>{alert.ticker}</strong>
                      <span>{alert.title}</span>
                    </div>
                    <p>{alert.message}</p>
                  </div>
                  {alert.score !== null && (
                    <span className="score-badge">{alert.score}</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No alerts have been generated yet." />
          )}
        </div>
      </section>

      <section className="two-column">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Money Rotation</span>
              <h2>Leading Groups</h2>
            </div>
            <Link href="/rotation" className="text-link">
              Full table →
            </Link>
          </div>

          {data.rotation_top.length ? (
            <div className="rotation-cards">
              {data.rotation_top.map((row) => (
                <div className="rotation-card" key={row.ticker}>
                  <div className="rotation-card-top">
                    <div>
                      <strong>{row.ticker}</strong>
                      <span>{row.name}</span>
                    </div>
                    <span className="score-badge">{row.rotation_score}</span>
                  </div>
                  <div className="mini-stats">
                    <span>1D {pct(row.return_1d)}</span>
                    <span>5D {pct(row.return_5d)}</span>
                    <span>20D {pct(row.return_20d)}</span>
                  </div>
                  <div className="progress">
                    <span style={{ width: `${row.rotation_score}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="Refresh SPY and sector ETFs to populate money rotation." />
          )}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Upcoming Earnings</span>
              <h2>Next 14 Days</h2>
            </div>
            <Link href="/earnings" className="text-link">
              Calendar →
            </Link>
          </div>

          {data.upcoming_earnings.length ? (
            <div className="earnings-list">
              {data.upcoming_earnings.slice(0, 7).map((event) => (
                <div className="earnings-row" key={`${event.ticker}-${event.report_date}`}>
                  <div className="date-box">
                    <span>{new Date(`${event.report_date}T00:00:00`).toLocaleDateString("en-US", { month: "short" })}</span>
                    <strong>{new Date(`${event.report_date}T00:00:00`).getDate()}</strong>
                  </div>
                  <div className="grow">
                    <div className="line-between">
                      <strong>{event.ticker}</strong>
                      <span className="impact-badge">
                        {event.impact_score}/10
                      </span>
                    </div>
                    <span>{event.company_name}</span>
                    <small>{event.sector}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No high-impact earnings are stored for the next 14 days." />
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Technical Watchlist</span>
            <h2>Daily Setups</h2>
          </div>
        </div>

        {data.technical_watchlist.length ? (
          <div className="card-grid">
            {data.technical_watchlist.map((item) => (
              <Link
                href={`/stocks/${item.ticker}`}
                className="stock-card"
                key={item.ticker}
              >
                <div className="line-between">
                  <strong>{item.ticker}</strong>
                  <span className="score-badge">{item.technical_score}</span>
                </div>
                <div className="stock-price">${fmt(item.price)}</div>
                <div className="mini-stats">
                  <span>RSI {fmt(item.rsi14, 1)}</span>
                  <span>{item.trend}</span>
                </div>
                <div className="progress">
                  <span style={{ width: `${item.technical_score}%` }} />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState text="No technical watchlist data is available yet." />
        )}
      </section>
    </>
  );
}
