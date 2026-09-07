"""Trigger one hosted refresh without disclosing portfolio details in CI logs."""

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

JOBS = {
    "daily": "/api/jobs/daily/run",
    "screener": "/api/jobs/screener/run",
    "earnings": "/api/jobs/weekly-earnings/run",
    "alerts": "/api/jobs/alerts/run",
}
SCHEDULES = {"15 23 * * 1-5": "daily", "35 23 * * 1-5": "screener", "0 10 * * 0": "earnings"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    job = os.environ.get("JOB") or SCHEDULES.get(os.environ.get("SCHEDULE", ""))
    if job not in JOBS:
        raise SystemExit("Choose daily, screener, earnings or alerts.")
    origin = os.environ.get("API_BASE_URL", "").rstrip("/")
    url = urlsplit(origin)
    token = os.environ.get("API_ACCESS_TOKEN", "")
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
        raise SystemExit("Configure API_BASE_URL with the HTTPS backend origin.")
    if not token:
        raise SystemExit("Configure the API_ACCESS_TOKEN Actions secret.")
    opener = build_opener(NoRedirect())
    for attempt in range(5):
        try:
            with opener.open(origin + "/api/health", timeout=90) as response:
                if json.load(response).get("status") != "ok":
                    raise ValueError("Backend health check failed")
            break
        except (HTTPError, URLError, TimeoutError, ValueError):
            if attempt == 4:
                raise SystemExit("Backend did not become ready. Check the hosting dashboard.")
            time.sleep(20)
    request = Request(origin + JOBS[job], data=b"", method="POST", headers={
        "Authorization": "Bearer " + token, "Accept": "application/json",
    })
    try:
        with opener.open(request, timeout=900) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"Job request returned HTTP {exc.code}. Check private backend logs.") from None
    except (URLError, TimeoutError, ValueError):
        raise SystemExit("The job response was unavailable. Check its history before retrying; it may still be running.") from None
    status = result.get("status")
    if status not in {"SUCCESS", "PARTIAL", "FAILED"}:
        raise SystemExit("Backend returned an unexpected job result.")
    print(f"{job}: {status}")
    if status != "SUCCESS":
        raise SystemExit("Open the dashboard's System page for details. No private data is printed here.")


if __name__ == "__main__":
    main()
