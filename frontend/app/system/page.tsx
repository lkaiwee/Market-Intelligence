"use client";

import { useEffect, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import type { JobStatus } from "@/lib/types";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

type JobRun = {
  id: number;
  job_name: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  detail: string | null;
};

type Result = {
  job_name: string;
  status: string;
  detail: string;
};

export default function SystemPage() {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [history, setHistory] = useState<JobRun[] | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);

      const [statusData, historyData] = await Promise.all([
        apiGet<JobStatus>("/api/jobs/status"),
        apiGet<JobRun[]>("/api/jobs/history?limit=30"),
      ]);

      setStatus(statusData);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function run(path: string, name: string) {
    setBusy(name);
    setResult(null);

    try {
      const output = await apiPost<Result>(path);
      setResult(output);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error && !status) {
    return (
      <>
        <PageHeader
          title="System"
          subtitle="Scheduler status, manual jobs and execution history."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!status || !history) return <Loading />;

  return (
    <>
      <PageHeader
        title="System"
        subtitle="Scheduler status, manual jobs and execution history."
      />

      {error && <ErrorBox message={error} />}

      <section className="metric-grid">
        <div className="metric-card">
          <span className="eyebrow">Scheduler</span>
          <strong>
            {status.scheduler_running ? "RUNNING" : "STOPPED"}
          </strong>
          <span className="muted">{status.timezone}</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Daily Market</span>
          <strong>{status.daily_schedule}</strong>
          <span className="muted">Yahoo prices + rotation</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Blue-Chip Screener</span>
          <strong>Tue-Sat 07:35</strong>
          <span className="muted">Prices daily · fundamentals ≤ 7 days old</span>
        </div>

        <div className="metric-card">
          <span className="eyebrow">Weekly Earnings</span>
          <strong>{status.weekly_schedule}</strong>
          <span className="muted">Yahoo earnings calendar</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Manual Controls</span>
            <h2>Jobs</h2>
          </div>
        </div>

        <div className="action-grid">
          <button
            className="action-card"
            onClick={() =>
              run("/api/jobs/alerts/run", "alerts")
            }
            disabled={busy !== null}
          >
            <strong>Generate Alerts</strong>
            <span>Uses stored data only.</span>
            <small>
              {busy === "alerts" ? "Running…" : "Run now"}
            </small>
          </button>

          <button
            className="action-card"
            onClick={() =>
              run("/api/jobs/daily/run?force=false", "daily")
            }
            disabled={busy !== null}
          >
            <strong>Daily Market Refresh</strong>
            <span>Yahoo prices, sectors and money rotation.</span>
            <small>
              {busy === "daily" ? "Running…" : "Run now"}
            </small>
          </button>

          <button
            className="action-card"
            onClick={() =>
              run(
                "/api/jobs/screener/run?force_fundamentals=false",
                "screener"
              )
            }
            disabled={busy !== null}
          >
            <strong>Blue-Chip Screener Update</strong>
            <span>
              Refreshes all blue-chip prices and missing/stale Yahoo fundamentals.
            </span>
            <small>
              {busy === "screener" ? "Running…" : "Run now"}
            </small>
          </button>

          <button
            className="action-card"
            onClick={() =>
              run("/api/jobs/weekly-earnings/run", "earnings")
            }
            disabled={busy !== null}
          >
            <strong>Upcoming Earnings Refresh</strong>
            <span>Yahoo 90-day blue-chip earnings calendar.</span>
            <small>
              {busy === "earnings" ? "Running…" : "Run now"}
            </small>
          </button>
        </div>

        {result && (
          <div className={`job-result ${result.status}`}>
            <strong>
              {result.job_name}: {result.status}
            </strong>
            <span>{result.detail}</span>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Scheduled Jobs</span>
            <h2>Next Runs</h2>
          </div>
        </div>

        <div className="card-grid">
          {status.jobs.map((job) => (
            <div className="stock-card" key={job.id}>
              <div className="line-between">
                <strong>{job.id}</strong>
                <span className="status-dot" />
              </div>

              <div className="muted" style={{ marginTop: 12 }}>
                {job.next_run_time
                  ? new Date(job.next_run_time).toLocaleString()
                  : "No next run"}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Execution History</span>
            <h2>Recent Jobs</h2>
          </div>

          <button className="button" onClick={load}>
            Refresh
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Status</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Detail</th>
              </tr>
            </thead>

            <tbody>
              {history.map((job) => (
                <tr key={job.id}>
                  <td>
                    <strong>{job.job_name}</strong>
                  </td>
                  <td>
                    <span className={`job-status ${job.status}`}>
                      {job.status}
                    </span>
                  </td>
                  <td>
                    {new Date(job.started_at).toLocaleString()}
                  </td>
                  <td>
                    {job.finished_at
                      ? new Date(job.finished_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="detail-cell">
                    {job.detail || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
