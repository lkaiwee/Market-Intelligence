# GitHub Pages frontend

The dashboard frontend is published at https://lkaiwee.github.io/Market-Intelligence/.
GitHub Pages serves static HTML, CSS and JavaScript. It does not run this repository's FastAPI backend, PostgreSQL database or scheduled refresh jobs.

When no backend URL is configured, the site explicitly displays **Backend not connected**. No market data or portfolio data is included in the public build, and the frontend does not send requests to a visitor's localhost.

## Publishing

In repository Settings → Pages, choose **GitHub Actions** as the source. The `Deploy dashboard to GitHub Pages` workflow builds and deploys frontend changes pushed to `main`. It can also be run manually.

The Pages build uses Next.js static export with the repository base path and trailing slashes. Stock analysis links use `/stocks/?ticker=NVDA` so any ticker can be selected without needing a server to create new pages. Normal local `npm run dev` and `npm run build` keep the server build unless `GITHUB_PAGES=true` is set.

## Connect the backend

1. Host the FastAPI app and a persistent PostgreSQL database on a service that supports Python. Keep the scheduler process running for automatic refreshes.
2. Enable `API_AUTH_REQUIRED=true` and configure a private `API_ACCESS_TOKEN` of at least 32 characters. The dashboard prompts for this owner token; never put it in the public frontend build. See `README_HOSTED_API.md` for the free Render and Neon deployment.
3. Configure FastAPI CORS to allow the frontend origin `https://lkaiwee.github.io` (without the repository path).
4. In repository Settings → Secrets and variables → Actions → Variables, add `NEXT_PUBLIC_API_BASE_URL` with the backend's HTTPS origin, for example `https://your-api.example.com`. Do not include `/api`, credentials or secret tokens. This URL is embedded in the public frontend JavaScript.
5. Run the Pages deployment workflow again. The backend connection notice disappears and API requests use the configured URL.

Existing local database contents are not uploaded by this deployment. Backend/database deployment and data migration are separate from publishing the frontend.

## Validate locally

From `frontend`, run `npm ci`, then set `GITHUB_PAGES=true` and `PAGES_BASE_PATH=/Market-Intelligence` before `npm run build`. The generated site is in `frontend/out` and must be served under `/Market-Intelligence/` when using that base path.
