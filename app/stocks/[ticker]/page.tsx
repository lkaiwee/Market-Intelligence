"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { apiGet } from "@/lib/api";
import type { InvestmentAnalysis, TechnicalAnalysis } from "@/lib/types";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";
import { ScoreRing } from "@/components/ScoreRing";

function fmt(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export default function StockDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = String(params.ticker || "").toUpperCase();

  const [technical, setTechnical] = useState<TechnicalAnalysis | null>(null);
  const [investment, setInvestment] = useState<InvestmentAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setError(null);
        const technicalData = await apiGet<TechnicalAnalysis>(
          `/api/stocks/${ticker}/analysis`
        );
        setTechnical(technicalData);

        try {
          const investmentData = await apiGet<InvestmentAnalysis>(
            `/api/stocks/${ticker}/investment-analysis`
          );
          setInvestment(investmentData);
        } catch {
          setInvestment(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    if (ticker) load();
  }, [ticker]);

  if (error) {
    return (
      <>
        <PageHeader
          title={ticker}
          subtitle="Stock technical and investment analysis."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!technical) return <Loading />;

  return (
    <>
      <PageHeader
        title={ticker}
        subtitle={
          investment?.company_name
            ? `${investment.company_name} · ${investment.sector || ""}`
            : "Technical analysis"
        }
      />

      <section className="stock-hero">
        <div>
          <span className="eyebrow">Latest Price</span>
          <div className="hero-price">${fmt(technical.price)}</div>
          <div className="ticker-chip-row">
            <span className="ticker-chip">{technical.trend}</span>
            <span className="ticker-chip">{technical.signal}</span>
            <span className="ticker-chip">{technical.latest_date}</span>
          </div>
        </div>

        <ScoreRing
          score={
            investment
              ? investment.opportunity_score
              : technical.technical_score
          }
          label={investment ? "Opportunity" : "Technical"}
        />
      </section>

      <section className="score-grid">
        <div className="metric-card">
          <span className="eyebrow">Technical</span>
          <strong>{technical.technical_score}/100</strong>
        </div>
        <div className="metric-card">
          <span className="eyebrow">Fundamental</span>
          <strong>{investment ? `${investment.fundamental_score}/100` : "—"}</strong>
        </div>
        <div className="metric-card">
          <span className="eyebrow">Valuation</span>
          <strong>{investment ? `${investment.valuation_score}/100` : "—"}</strong>
        </div>
        <div className="metric-card">
          <span className="eyebrow">Leadership</span>
          <strong>{investment ? `${investment.leadership_score}/100` : "—"}</strong>
        </div>
      </section>

      <section className="two-column">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Trend</span>
              <h2>Technical Indicators</h2>
            </div>
          </div>

          <div className="detail-grid large">
            <div><span>RSI 14</span><strong>{fmt(technical.rsi14, 1)}</strong></div>
            <div><span>EMA 9</span><strong>{fmt(technical.ema9)}</strong></div>
            <div><span>EMA 20</span><strong>{fmt(technical.ema20)}</strong></div>
            <div><span>SMA 20</span><strong>{fmt(technical.sma20)}</strong></div>
            <div><span>SMA 50</span><strong>{fmt(technical.sma50)}</strong></div>
            <div><span>SMA 200</span><strong>{fmt(technical.sma200)}</strong></div>
            <div><span>MACD</span><strong>{fmt(technical.macd, 4)}</strong></div>
            <div><span>MACD Signal</span><strong>{fmt(technical.macd_signal, 4)}</strong></div>
            <div><span>ATR 14</span><strong>{fmt(technical.atr14)}</strong></div>
            <div><span>ATR %</span><strong>{fmt(technical.atr_pct)}%</strong></div>
            <div><span>Volume Ratio</span><strong>{fmt(technical.volume_ratio)}</strong></div>
            <div><span>History Bars</span><strong>{technical.history_bars}</strong></div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Pullback</span>
              <h2>Price Position</h2>
            </div>
          </div>

          <div className="detail-grid large">
            <div>
              <span>52W High</span>
              <strong>${fmt(technical.high_52w)}</strong>
            </div>
            <div>
              <span>52W Pullback</span>
              <strong>{fmt(technical.pullback_52w_pct)}%</strong>
            </div>
            <div>
              <span>Available High</span>
              <strong>${fmt(technical.high_available)}</strong>
            </div>
            <div>
              <span>Available Pullback</span>
              <strong>{fmt(technical.pullback_available_pct)}%</strong>
            </div>
          </div>

          {investment && (
            <>
              <div className="panel-divider" />
              <div className="detail-grid large">
                <div><span>Forward P/E</span><strong>{fmt(investment.forward_pe)}</strong></div>
                <div><span>PEG</span><strong>{fmt(investment.peg_ratio)}</strong></div>
                <div><span>Revenue Growth</span><strong>{fmt(investment.revenue_growth_yoy !== null ? investment.revenue_growth_yoy * 100 : null)}%</strong></div>
                <div><span>Earnings Growth</span><strong>{fmt(investment.earnings_growth_yoy !== null ? investment.earnings_growth_yoy * 100 : null)}%</strong></div>
                <div><span>FCF Yield</span><strong>{fmt(investment.free_cash_flow_yield !== null ? investment.free_cash_flow_yield * 100 : null)}%</strong></div>
                <div><span>Debt / Equity</span><strong>{fmt(investment.debt_to_equity)}</strong></div>
              </div>
            </>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Model Notes</span>
            <h2>Warnings & Limitations</h2>
          </div>
        </div>
        <ul className="warning-list">
          {[...(technical.warnings || []), ...(investment?.warnings || [])]
            .filter((value, index, all) => all.indexOf(value) === index)
            .map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
        </ul>
      </section>
    </>
  );
}
