import type { NextConfig } from "next";

const githubPages = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  ...(githubPages
    ? {
        output: "export",
        basePath: process.env.PAGES_BASE_PATH ?? "/Market-Intelligence",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
  env: {
    NEXT_PUBLIC_GITHUB_PAGES: String(githubPages),
  },
};

export default nextConfig;
