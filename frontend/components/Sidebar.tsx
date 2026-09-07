"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Dashboard", icon: "◫" },
  { href: "/alerts", label: "Alerts", icon: "◉" },
  { href: "/rotation", label: "Money Rotation", icon: "↗" },
  { href: "/screener", label: "Screener", icon: "⌕" },
  { href: "/earnings", label: "Earnings", icon: "◷" },
  { href: "/universe", label: "Stock Universe", icon: "+" },
  { href: "/system", label: "System", icon: "⚙" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">MI</div>
        <div>
          <strong>Market Intelligence</strong>
          <span>Local Terminal</span>
        </div>
      </div>

      <nav>
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${active ? "active" : ""}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot" />
        FastAPI + PostgreSQL
      </div>
    </aside>
  );
}
