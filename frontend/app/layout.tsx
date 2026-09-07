import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { BackendNotice } from "@/components/BackendNotice";

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
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
