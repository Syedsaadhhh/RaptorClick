/* Obsidian Sentinel / overview landing page: introduction first, directory pathways second, raptor as the watchful visual anchor. */

import { ArrowDownRight, ArrowUpRight, Braces, GitBranch, Layers3, ShieldCheck } from "lucide-react";
import { Link } from "wouter";
import { lazy, Suspense, useRef } from "react";

const HeroFluidCanvas = lazy(() => import("@/components/HeroFluidCanvas"));
import DirectoryChrome from "@/components/DirectoryChrome";
import StateMachinePreview from "@/components/StateMachinePreview";
import { ASSET_URLS } from "@/lib/assets";

const overviewMetrics = [
  { value: "12", label: "run states", detail: "from idle to safe completion" },
  { value: "04", label: "policy gates", detail: "visible before execution" },
  { value: "03", label: "auction paths", detail: "normalized for fit" },
];

const heroProofs = [
  { value: "100%", label: "deterministic engine" },
  { value: "0", label: "synthetic yield claims" },
  { value: "12", label: "observable run states" },
];

const pathways = [
  { href: "/architecture", code: "01", title: "System Architecture", description: "See how observation, stress, auction, governance, and execution connect.", icon: <GitBranch size={17} /> },
  { href: "/control-room", code: "02", title: "Control Room", description: "Enter the live simulation and replay the complete protection cycle.", icon: <ShieldCheck size={17} /> },
  { href: "/audit", code: "03", title: "Audit / Receipts", description: "Trace state changes, paper orders, and execution outcomes without hidden reasoning.", icon: <Layers3 size={17} /> },
  { href: "/docs", code: "04", title: "Data Contracts", description: "Review the typed models and adapter boundary behind every dashboard surface.", icon: <Braces size={17} /> },
];

export default function Overview() {
  const heroRef = useRef<HTMLElement | null>(null);

  return (
    <main className="app-shell overview-shell">
      <div className="atmosphere-layer" style={{ backgroundImage: `url(${ASSET_URLS.atmosphere})` }} />
      <div className="noise-layer" />
      <DirectoryChrome active="overview" />
      <div className="page-frame overview-frame">
        <section className="overview-hero" ref={heroRef}>
          <Suspense fallback={null}><HeroFluidCanvas hostRef={heroRef} /></Suspense>
          <div className="overview-copy">
            <p className="eyebrow">RaptorClick / protective intelligence layer</p>
            <h1>Protection is a<br /><em>state machine.</em></h1>
            <p className="overview-lede">RaptorClick turns portfolio insurance into an observable, replayable operating model. It watches the book, stress-tests the risk, auctions executable protection, and only routes an order after the governor clears the path.</p>
            <div className="overview-inline-proofs" aria-label="RaptorClick operating guarantees">
              {heroProofs.map((proof) => <span key={proof.label}><strong>{proof.value}</strong><small>{proof.label}</small></span>)}
            </div>
            <div className="overview-cta-row">
              <Link href="/control-room" className="overview-cta">Launch Control Room <ArrowUpRight size={15} /></Link>
              <Link href="/architecture" className="overview-secondary-cta">Explore the architecture <ArrowDownRight size={14} /></Link>
            </div>
            <div className="overview-proof"><span>read-only simulation</span><span>no fabricated returns</span></div>
          </div>
          <div className="overview-art-stage overview-preview-stage">
            <StateMachinePreview />
          </div>
        </section>

        <section className="overview-metrics" aria-label="RaptorClick architecture metrics">
          {overviewMetrics.map((metric) => <div className="overview-metric" key={metric.label}><strong>{metric.value}</strong><span>{metric.label}</span><small>{metric.detail}</small></div>)}
        </section>

        <section className="directory-section">
          <div className="directory-section-heading"><div><p className="eyebrow">Directory / choose a surface</p><h2>Start with the question you need answered.</h2></div><p>Every route keeps the same operating vocabulary, so a handoff from overview to execution never loses context.</p></div>
          <div className="pathway-grid">{pathways.map((pathway) => <Link href={pathway.href} className="pathway-card" key={pathway.href}><div className="pathway-top"><span className="pathway-code">{pathway.code}</span><span className="pathway-icon">{pathway.icon}</span></div><h3>{pathway.title}</h3><p>{pathway.description}</p><span className="pathway-link">Open directory <ArrowUpRight size={14} /></span></Link>)}</div>
        </section>

        <section className="overview-principles glass-panel"><div><p className="eyebrow">Operating thesis</p><h2>Make the protection decision legible.</h2></div><div className="principle-copy"><p>The important output is not a confident-looking number. It is a clean chain of observable inputs, bounded decisions, and explicit receipts.</p><Link href="/docs" className="text-link">Read the contracts <ArrowUpRight size={13} /></Link></div></section>
        <footer className="app-footer"><span><span className="green-dot" /> RaptorClick / overview directory</span><span className="mono">DEMO DATA · READ ONLY · v0.9.7</span><span className="mono">© 2026 RAPTORCLICK</span></footer>
      </div>
    </main>
  );
}
