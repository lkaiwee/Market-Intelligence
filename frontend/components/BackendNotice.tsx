export function BackendNotice() {
  if (
    process.env.NEXT_PUBLIC_GITHUB_PAGES !== "true" ||
    process.env.NEXT_PUBLIC_API_BASE_URL
  ) {
    return null;
  }

  return (
    <div role="status" className="panel" style={{ padding: "16px 20px", marginBottom: 24 }}>
      <strong>Frontend online · Backend not connected</strong>
      <p style={{ margin: "8px 0 0" }}>
        GitHub Pages hosts this dashboard’s interface. Live market data, saved
        portfolio positions and scheduled refreshes need the Python API and
        database on a separate host.{" "}
        <a href="https://github.com/lkaiwee/Market-Intelligence/blob/main/README_GITHUB_PAGES.md">
          Backend setup
        </a>
      </p>
    </div>
  );
}
