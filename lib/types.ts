export type RotationRow = {
  rank: number;
  ticker: string;
  name: string;
  group: string;
  latest_date: string;
  price: number;
  return_1d: number;
  return_5d: number;
  return_20d: number;
  relative_1d: number;
  relative_5d: number;
  relative_20d: number;
  momentum_20d: number;
  rotation_score: number;
  flow: string;
};

export type AlertItem = {
  id: number;
  alert_date: string;
  ticker: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  score: number | null;
  price: string | number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type InvestmentAnalysis = {
  ticker: string;
  company_name: string | null;
  sector: string | null;
  industry: string | null;
  price: number;
  latest_date: string;
  technical_score: number;
  fundamental_score: number;
  valuation_score: number;
  leadership_score: number;
  opportunity_score: number;
  investment_signal: string;
  pullback_pct: number;
  rsi14: number | null;
  trend: string;
  forward_pe: number | null;
  peg_ratio: number | null;
  free_cash_flow_ttm: number | null;
  free_cash_flow_yield: number | null;
  revenue_growth_yoy: number | null;
  earnings_growth_yoy: number | null;
  debt_to_equity: number | null;
  warnings: string[];
};

export type TechnicalAnalysis = {
  ticker: string;
  latest_date: string;
  history_bars: number;
  price: number;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  ema9: number | null;
  ema20: number | null;
  rsi14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  atr14: number | null;
  atr_pct: number | null;
  avg_volume20: number | null;
  volume_ratio: number | null;
  high_available: number;
  pullback_available_pct: number;
  high_52w: number | null;
  pullback_52w_pct: number | null;
  trend: string;
  technical_score: number;
  signal: string;
  warnings: string[];
};

export type EarningsEvent = {
  ticker: string;
  company_name: string;
  sector: string;
  report_date: string;
  fiscal_date_ending: string | null;
  eps_estimate: number | null;
  currency: string | null;
  impact_score: number;
  impact_level: string;
  impact_note: string;
  related_tickers: string[];
};

export type JobStatus = {
  scheduler_enabled: boolean;
  scheduler_running: boolean;
  timezone: string;
  daily_schedule: string;
  weekly_schedule: string;
  watchlist: string[];
  jobs: {
    id: string;
    next_run_time: string | null;
  }[];
};

export type Dashboard = {
  generated_at: string;
  market_regime: string | null;
  risk_on_score: number | null;
  strongest_rotation: string[];
  rotation_top: RotationRow[];
  alerts: AlertItem[];
  top_investment_opportunities: InvestmentAnalysis[];
  technical_watchlist: TechnicalAnalysis[];
  upcoming_earnings: EarningsEvent[];
  scheduler: JobStatus;
};
