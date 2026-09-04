/* Obsidian Sentinel / directory chrome: a quiet navigation spine connecting the overview, architecture, control room, and audit surfaces. */

import { ArrowUpRight, ChevronRight, CircleDot } from "lucide-react";
import { Link, useLocation } from "wouter";

type DirectoryChromeProps = {
  active: "overview" | "architecture" | "control-room" | "audit" | "docs";
};

const routes = [
  { key: "overview", label: "Overview", href: "/" },
  { key: "architecture", label: "System Architecture", href: "/architecture" },
  { key: "control-room", label: "Control Room", href: "/control-room" },
  { key: "audit", label: "Audit / Receipts", href: "/audit" },
] as const;

export default function DirectoryChrome({ active }: DirectoryChromeProps) {
  const [, setLocation] = useLocation();
  return (
    <>
      <header className="topbar directory-topbar">
        <Link href="/" className="brand-lockup brand-lockup-text" aria-label="RaptorClick overview">
          <div>
            <div className="brand-name"><span className="brand-wordmark">RAPTOR</span><span className="brand-wordmark-tail">CLICK</span></div>
            <div className="brand-subtitle">PROTECTIVE INTELLIGENCE / DIRECTORY</div>
          </div>
        </Link>
        <nav className="directory-nav" aria-label="Primary directory">
          {routes.map((route) => (
            <Link key={route.key} href={route.href} className={`directory-link ${active === route.key ? "directory-link-active" : ""}`} aria-current={active === route.key ? "page" : undefined}>
              <span>{route.label}</span>
              {active === route.key && <CircleDot size={9} />}
            </Link>
          ))}
        </nav>
        <div className="topbar-right"><span className="operator-label">OPERATOR <strong>GROWTH / 07</strong></span><div className="avatar-chip">G7</div></div>
      </header>
      <div className="directory-crumbbar" aria-label="Breadcrumb">
        <div className="breadcrumb-list">
          {routes.map((route, index) => (
            <span className="breadcrumb-item" key={route.key}>
              {index > 0 && <ChevronRight size={12} />}
              <Link href={route.href} className={active === route.key ? "breadcrumb-active" : ""}>{route.label}</Link>
            </span>
          ))}
        </div>
        <button type="button" className="directory-console-link" onClick={() => setLocation("/docs")}>
          <span className="green-dot" /> DATA CONTRACTS <ArrowUpRight size={12} />
        </button>
      </div>
    </>
  );
}

