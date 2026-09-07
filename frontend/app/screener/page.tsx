"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPost } from "@/lib/api";
import type { InvestmentAnalysis, TechnicalAnalysis } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

type ScreenerRefreshResult = {
  universe_size: number;
  prices_succeeded: number;
  prices_failed: number;
  price_rows_processed: number;
  price_failures: string[];
  fundamentals_refreshed: number;
  fundamentals_skipped_fresh: number;
  fundamentals_failed: number;
  fundamental_failures: string[];
  newest_market_date: string | null;
};

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export default function ScreenerPage() {
  const [investments, setInvestments] = useState<InvestmentAnalysis[] | null>(null);
  const [technical, setTechnical] = useState<TechnicalAnalysis[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<ScreenerRefreshResult | null>(null);

  async function load() {
    try {
      setError(null);

      const [investmentData, technicalData] = await Promise.all([
        apiGet<InvestmentAnalysis[]>(
          "/api/investment-screener?min_score=0&limit=100"
        ),
        apiGet<TechnicalAnalysis[]>(
          "/api/screener?min_score=0&limit=100"
        ),
      ]);

      setInvestments(investmentData);
      setTechnical(technicalData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function updateScreener() {
    setSyncing(true);
    setSyncResult(null);

    try {
      const result = await apiPost<ScreenerRefreshResult>(
        "/api/screener/refresh?force_fundamentals=false"
      );

      setSyncResult(result);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error && !investments && !technical) {
    return (
      <>
        <PageHeader
          title="Investment Screener"
          subtitle="Daily blue-chip ranking using technical, fundamental, valuation and leadership scores."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!investments || !technical) return <Loading />;

  return (
    <>
      <PageHeader
        title="Investment Screener"
        subtitle="Daily blue-chip ranking using technical, fundamental, valuation and leadership scores."
      />

      <div className="toolbar">
        <button
          className="button primary"
          onClick={updateScreener}
          disabled={syncing}
        >
          {syncing ? "Updating Blue-Chip Universe…" : "Update Blue-Chip Screener"}
        </button>

        <button className="button" onClick={load} disabled={syncing}>
          Refresh view
        </button>

        <span className="muted">
          Automatic update: Tue-Sat 07:35 SGT
        </span>
      </div>

      {syncing && (
        <div className="job-result PARTIAL">
          <strong>Blue-chip sync is running</strong>
          <span>
            The first sync can take 1-3 minutes because missing Yahoo fundamentals
            are being populated for the full universe. Do not refresh the browser.
          </span>
        </div>
      )}

      {syncResult && (
        <div
          className={`job-result ${
            syncResult.fundamentals_failed === 0 &&
            syncResult.prices_failed === 0
              ? "SUCCESS"
              : "PARTIAL"
          }`}
        >
          <strong>
            Screener update complete · {syncResult.universe_size} blue-chip stocks
          </strong>
          <span>
            Price series: {syncResult.prices_succeeded} succeeded /{" "}
            {syncResult.prices_failed} failed. Fundamentals:{" "}
            {syncResult.fundamentals_refreshed} refreshed,{" "}
            {syncResult.fundamentals_skipped_fresh} reused,{" "}
            {syncResult.fundamentals_failed} failed.
            {syncResult.newest_market_date
              ? ` Latest market date: ${syncResult.newest_market_date}.`
              : ""}
          </span>
        </div>
      )}

      {error && <ErrorBox message={error} />}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Full Investment Model</span>
            <h2>Blue-Chip Opportunity Ranking</h2>
          </div>
          <span className="muted">
            {investments.length} companies with complete investment analysis
          </span>
        </div>

        {investments.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Ticker</th>
                  <th>Opportunity</th>
                  <th>Technical</th>
                  <th>Fundamental</th>
                  <th>Valuation</th>
                  <th>Leadership</th>
                  <th>Pullback</th>
                  <th>Fwd P/E</th>
                  <th>Signal</th>
                </tr>
              </thead>
              <tbody>
                {investments.map((item, index) => (
                  <tr key={item.ticker}>
                    <td>#{index + 1}</td>
                    <td>
                      <Link
                        className="ticker-link"
                        href={`/stocks/?ticker=${encodeURIComponent(item.ticker)}`}
                      >
                        {item.ticker}
                      </Link>
                      <div className="subcell">{item.company_name}</div>
                    </td>
                    <td>
                      <span className="score-badge big">
                        {item.opportunity_score}
                      </span>
                    </td>
                    <td>{item.technical_score}</td>
                    <td>{item.fundamental_score}</td>
                    <td>{item.valuation_score}</td>
                    <td>{item.leadership_score}</td>
                    <td className={item.pullback_pct < 0 ? "negative" : "positive"}>
                      {fmt(item.pullback_pct)}%
                    </td>
                    <td>{fmt(item.forward_pe)}</td>
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
          <EmptyState text="Run Update Blue-Chip Screener once to populate Yahoo fundamentals and investment scores." />
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Technical-Only</span>
            <h2>All Stored Stocks & ETFs</h2>
          </div>
          <span className="muted">{technical.length} instruments</span>
        </div>

        {technical.length ? (
          <div className="card-grid">
            {technical.map((item) => (
              <Link
                href={`/stocks/?ticker=${encodeURIComponent(item.ticker)}`}
                className="stock-card"
                key={item.ticker}
              >
                <div className="line-between">
                  <strong>{item.ticker}</strong>
                  <span className="score-badge">
                    {item.technical_score}
                  </span>
                </div>

                <div className="stock-price">
                  ${fmt(item.price)}
                </div>

                <div className="mini-stats">
                  <span>RSI {fmt(item.rsi14, 1)}</span>
                  <span>{item.trend}</span>
                </div>

                <div className="mini-stats">
                  <span>SMA50 {fmt(item.sma50)}</span>
                  <span>SMA200 {fmt(item.sma200)}</span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState text="No technical analyses are available." />
        )}
      </section>
    </>
  );
}
