"use client";

import { useEffect, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import type { AlertItem } from "@/lib/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBox } from "@/components/ErrorBox";
import { Loading } from "@/components/Loading";
import { PageHeader } from "@/components/PageHeader";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function load() {
    try {
      setError(null);
      setAlerts(await apiGet<AlertItem[]>("/api/alerts?days=30"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function generate() {
    setRunning(true);
    try {
      await apiPost("/api/jobs/alerts/run");
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

  if (error && !alerts) {
    return (
      <>
        <PageHeader
          title="Alerts"
          subtitle="Persistent technical, investment, rotation and earnings alerts."
        />
        <ErrorBox message={error} />
      </>
    );
  }

  if (!alerts) return <Loading />;

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle="Persistent technical, investment, rotation and earnings alerts."
      />

      <div className="toolbar">
        <button className="button primary" onClick={generate} disabled={running}>
          {running ? "Generating…" : "Generate from stored data"}
        </button>
        <button className="button" onClick={load}>
          Refresh view
        </button>
      </div>

      {error && <ErrorBox message={error} />}

      <section className="panel">
        {alerts.length ? (
          <div className="alert-list">
            {alerts.map((alert) => (
              <div className="alert-row large" key={alert.id}>
                <div className="grow">
                  <div className="alert-title-line">
                    <span className={`severity ${alert.severity}`}>
                      {alert.severity}
                    </span>
                    <strong>{alert.ticker}</strong>
                    <span className="muted">{alert.alert_type}</span>
                  </div>
                  <h3>{alert.title}</h3>
                  <p>{alert.message}</p>
                  <small>
                    {alert.alert_date} · {new Date(alert.created_at).toLocaleString()}
                  </small>
                </div>
                {alert.score !== null && (
                  <span className="score-badge big">{alert.score}</span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="No alerts have been generated." />
        )}
      </section>
    </>
  );
}
