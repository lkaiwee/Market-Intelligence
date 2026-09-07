import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { BackendNotice } from "@/components/BackendNotice";
import { ApiAccessGate } from "@/components/ApiAccessGate";

export const metadata: Metadata = {
  title: "Market Intelligence",
  description: "Local stock market intelligence dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main-content">
            <BackendNotice />
            <ApiAccessGate>{children}</ApiAccessGate>
          </main>
        </div>
      </body>
    </html>
  );
}
