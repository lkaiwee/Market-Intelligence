# Hosted Python API and PostgreSQL

The frontend stays on GitHub Pages. The API runs on Render's Free web service; data is stored in a Neon Free PostgreSQL database. Only the static UI and source code are public. The API requires an owner access token for all data and write endpoints.

## Deploy

1. Create a Neon Free project near the API region (Singapore when available). Copy its pooled PostgreSQL connection string, including `sslmode=require`, into Render's private `DATABASE_URL` environment variable. Do not put it in the repository.
2. Create a Render Blueprint from `render.yaml`. It selects a **Free** Python service, a single worker, the health endpoint, the GitHub Pages CORS origin, and a generated `API_ACCESS_TOKEN`. `API_AUTH_REQUIRED=true` prevents startup without a sufficiently long token. The API normalizes Neon PostgreSQL URLs for the installed psycopg driver.
3. Keep the generated access token private. The dashboard asks for it before mounting its data pages and retains it only for that browser tab's session. Sign out clears the token and unmounts private data. Local development remains available without a token unless authentication is configured.
4. In GitHub Actions variables, set both `NEXT_PUBLIC_API_BASE_URL` and `API_BASE_URL` to the Render HTTPS origin, without `/api`. Add `API_ACCESS_TOKEN` as an Actions **secret**, not a variable. Never put the access token in a `NEXT_PUBLIC_*` variable.
5. Run the Pages workflow to rebuild the frontend with the API URL. Run the refresh workflow for `daily`, `screener`, and `earnings` to populate the new database.

## Scheduled refreshes

Render's in-process scheduler is disabled for this deployment. GitHub Actions invokes the actual API jobs at the existing Singapore schedules: Tue-Sat 07:15 for daily market data, Tue-Sat 07:35 for the screener, and Sunday 18:00 for earnings. These jobs wake the free API as part of the requested refresh. CI prints only job status, never portfolio holdings or job details.

GitHub may delay scheduled workflows and disables schedules on public repositories after 60 days of inactivity. Re-enable the workflow when necessary. A non-successful job is marked as a failed workflow; private details remain on the dashboard's System page. Do not immediately retry a timed-out mutation: the backend may still be running it.

## Free hosting limits

The API can sleep after inactivity, making the first visit slow. The database has a free storage and compute quota and can suspend compute when idle. Stay within each provider's Free plan; no paid upgrade is part of this setup. Unlike Render's expiring free database, Neon advertises a free plan without a time limit. Provider quotas and plans can change.

The database starts empty. Existing local database contents are not automatically migrated. Portfolio positions can be added through the unlocked dashboard. Rotate the owner token in Render and the matching GitHub Actions secret if it is disclosed; previous browser sessions will need the new token.

## Checks

Run `python -m unittest discover -s tests` from `backend` for access-control and configuration tests. Build the frontend with `GITHUB_PAGES=true`, `PAGES_BASE_PATH=/Market-Intelligence`, and the API URL configured to check the exported sign-in flow.
