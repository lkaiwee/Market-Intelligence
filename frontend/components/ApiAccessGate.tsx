"use client";

import { FormEvent, Fragment, ReactNode, useCallback, useEffect, useRef, useState } from "react";
import {
  API_ACCESS_REQUIRED_EVENT,
  checkApiAccess,
  getApiAccess,
  getApiAccessToken,
  hasApiBaseUrl,
  setApiAccessToken,
} from "@/lib/api";
import styles from "./ApiAccessGate.module.css";

type AccessState = "checking" | "locked" | "ready" | "unavailable";
const CONNECTION_TIMEOUT_MS = 120_000;

export function ApiAccessGate({ children }: { children: ReactNode }) {
  const configured = hasApiBaseUrl();
  const [state, setState] = useState<AccessState>(configured ? "checking" : "ready");
  const [protectedAccess, setProtectedAccess] = useState(false);
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [session, setSession] = useState(0);
  const operation = useRef(0);
  const pending = useRef<AbortController | null>(null);

  const lockAccess = useCallback((reason = "") => {
    operation.current += 1;
    pending.current?.abort();
    setApiAccessToken(null);
    setToken("");
    setSubmitting(false);
    setMessage(reason);
    setProtectedAccess(true);
    setSession((value) => value + 1);
    setState("locked");
  }, []);

  const connect = useCallback(async () => {
    const current = ++operation.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), CONNECTION_TIMEOUT_MS);
    setState("checking");
    setMessage("");

    try {
      const access = await getApiAccess(controller.signal);
      if (current !== operation.current) return;

      setProtectedAccess(access.authentication_required);
      if (!access.authentication_required) {
        setApiAccessToken(null);
        setState("ready");
        return;
      }

      const savedToken = getApiAccessToken();
      if (!savedToken) {
        setState("locked");
        return;
      }

      const valid = await checkApiAccess(savedToken, controller.signal);
      if (current !== operation.current) return;
      if (valid) {
        setState("ready");
      } else {
        lockAccess("Your saved access token was not accepted. Enter your current token.");
      }
    } catch {
      if (current === operation.current) setState("unavailable");
    } finally {
      window.clearTimeout(timeout);
    }
  }, [lockAccess]);

  useEffect(() => {
    if (!configured) return;
    const onAccessRequired = () => lockAccess("Your session needs a valid access token. Please sign in again.");
    window.addEventListener(API_ACCESS_REQUIRED_EVENT, onAccessRequired);
    void connect();

    return () => {
      operation.current += 1;
      pending.current?.abort();
      window.removeEventListener(API_ACCESS_REQUIRED_EVENT, onAccessRequired);
    };
  }, [configured, connect, lockAccess]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const candidate = token.trim();
    if (!candidate || submitting) return;

    const current = ++operation.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), CONNECTION_TIMEOUT_MS);
    setSubmitting(true);
    setMessage("");

    try {
      const valid = await checkApiAccess(candidate, controller.signal);
      if (current !== operation.current) return;

      if (valid) {
        setApiAccessToken(candidate);
        setToken("");
        setSession((value) => value + 1);
        setState("ready");
      } else {
        setToken("");
        setMessage("That access token was not accepted. Try again.");
      }
    } catch {
      if (current === operation.current) {
        setMessage("The API could not verify your token. Check your connection and try again.");
      }
    } finally {
      window.clearTimeout(timeout);
      if (current === operation.current) setSubmitting(false);
    }
  }

  if (!configured) return children;

  if (state === "ready") {
    return (
      <>
        {protectedAccess && (
          <div className={styles.sessionBar}>
            <span>Owner access active</span>
            <button type="button" className={styles.secondaryButton} onClick={() => lockAccess()}>
              Sign out
            </button>
          </div>
        )}
        <Fragment key={session}>{children}</Fragment>
      </>
    );
  }

  return (
    <section className={`panel ${styles.panel}`} aria-labelledby="api-access-title">
      <span className="eyebrow">Market Intelligence</span>
      <h1 id="api-access-title">
        {state === "checking" ? "Connecting to your dashboard" : state === "unavailable" ? "API unavailable" : "Owner access"}
      </h1>

      {state === "checking" && (
        <p role="status">Checking the API connection and your session. The first connection may take a moment.</p>
      )}

      {state === "unavailable" && (
        <>
          <p role="alert">We could not connect to the dashboard API. Check your connection or try again once the service is running.</p>
          <button type="button" className={styles.primaryButton} onClick={() => void connect()}>Retry connection</button>
        </>
      )}

      {state === "locked" && (
        <>
          <p>Enter your owner access token to load market data and manage your portfolio.</p>
          <form onSubmit={signIn} className={styles.form}>
            <label htmlFor="owner-access-token">Access token</label>
            <input
              id="owner-access-token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              required
              disabled={submitting}
              aria-describedby="owner-access-help owner-access-message"
            />
            <p id="owner-access-help" className={styles.help}>Your token is kept for this browser tab’s session. Sign out to remove it.</p>
            <p id="owner-access-message" role="alert" className={styles.error}>{message}</p>
            <button type="submit" className={styles.primaryButton} disabled={submitting || !token.trim()}>
              {submitting ? "Verifying access…" : "Open dashboard"}
            </button>
          </form>
        </>
      )}
    </section>
  );
}
