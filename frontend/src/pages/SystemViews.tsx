/* Obsidian Sentinel / directory views: explain the operating model and expose the demo contracts without hiding decisions behind prose. */

import { ArrowUpRight, Braces, CheckCircle2, ChevronRight, CircleDot, Database, GitBranch, Layers3, Server, ShieldCheck, TerminalSquare } from "lucide-react";
import { Link } from "wouter";
import DirectoryChrome from "@/components/DirectoryChrome";
import { getHedgeRun } from "@/demo/mockData";
import { RUN_STATES } from "@/demo/models";

const architectureNodes = [
  { code: "01", title: "Observe", description: "Load a typed portfolio snapshot and preserve the source timestamp before any scenario runs.", color: "green", icon: <Database size={17} /> },
  { code: "02", title: "Stress", description: "Apply bounded market paths to expose stressed loss and affected positions.", color: "cyan", icon: <GitBranch size={17} /> },
  { code: "03", title: "Auction", description: "Normalize executable bids by premium, coverage, contract count, and venue fit.", color: "lilac", icon: <Layers3 size={17} /> },
  { code: "04", title: "Govern", description: "Run compliance checks and record a passed, pending, or rejected verdict.", color: "amber", icon: <ShieldCheck size={17} /> },
  { code: "05", title: "Receipt", description: "Keep dry-run, submitted, filled, rejected, and failed order states explicit.", color: "green", icon: <CheckCircle2 size={17} /> },
];

const contracts = [
  { name: "PortfolioSnapshot", role: "Book identity, equity, drawdown, exposure, concentration, protection state", source: "demo/mockData.ts" },
  { name: "StressScenario", role: "Scenario name, severity tier, stressed loss, affected positions", source: "demo/mockData.ts" },
  { name: "HedgeBid", role: "Strategy, contract count, premium, estimated protection, ranking score", source: "demo/mockData.ts" },
  { name: "AuctionRanking", role: "Normalized ranking output used by the Hedge Auction panel", source: "demo/models.ts" },
  { name: "RiskVerdict", role: "Policy status plus explicit compliance checks and rationale", source: "demo/models.ts" },
  { name: "ExecutionReceipt", role: "Order label, status, detail, and mock execution identifier", source: "demo/mockData.ts" },
  { name: "HedgeRun", role: "The adapter-level aggregate returned for any RunState", source: "lib/demoApi.ts" },
];

function DirectoryShell({ active, children, eyebrow, title, lede, showCode = true }: { active: "architecture" | "docs" | "audit"; children: React.ReactNode; eyebrow: string; title: string; lede: string; showCode?: boolean }) {
  return <main className="app-shell directory-shell"><div className="atmosphere-layer" /><div className="noise-layer" /><DirectoryChrome active={active} /><div className="page-frame directory-frame"><section className={`directory-hero ${showCode ? "" : "directory-hero-solo"}`}><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{lede}</p></div>{showCode && <div className="directory-hero-code"><span className="mono">RAPTORCLICK / DIRECTORY</span><strong>readable by design</strong><span>Every surface has a route, a contract, and a receipt.</span></div>}</section>{children}<footer className="app-footer"><span><span className="green-dot" /> RaptorClick / directory surface</span><span className="mono">DEMO DATA · READ ONLY · v0.9.7</span><span className="mono">© 2026 RAPTORCLICK</span></footer></div></main>;
}

export function SystemArchitecture() {
  return <DirectoryShell active="architecture" showCode={false} eyebrow="System architecture / 01" title="The protection loop, in plain sight." lede="RaptorClick is a sequence of bounded decisions. This directory makes the handoff between observation, stress, auction, governance, and execution explicit before you enter the control room.">
    <section className="architecture-flow"><div className="directory-section-heading"><div><p className="eyebrow">State machine / five operating layers</p><h2>From portfolio signal to explicit receipt.</h2></div><Link href="/control-room" className="text-link">Launch the loop <ArrowUpRight size={13} /></Link></div><div className="architecture-list">{architectureNodes.map((node, index) => <div className={`architecture-node architecture-node-${node.color}`} key={node.code}><div className="architecture-node-head"><span className="pathway-code">{node.code}</span><span className="architecture-icon">{node.icon}</span></div><div><h3>{node.title}</h3><p>{node.description}</p></div>{index < architectureNodes.length - 1 && <ChevronRight className="architecture-arrow" size={17} />}</div>)}</div></section>
    <section className="architecture-bottom"><div className="glass-panel architecture-note"><p className="eyebrow">Invariant</p><h2>No order without a verdict.</h2><p>The selected structure can move through dry-run and paper routing, but the model never implies a fill until an explicit receipt says so.</p></div><div className="glass-panel architecture-note"><p className="eyebrow">Observable states</p><h2>{RUN_STATES.length} checkpoints.</h2><p>Each state can be deep-linked from the control room, making demos, QA, and handoffs reproducible.</p></div></section>
  </DirectoryShell>;
}

export function SystemDocs() {
  return <DirectoryShell active="docs" eyebrow="System docs / contracts" title="Contracts before components." lede="A clean adapter boundary keeps the interface replaceable. The current surface uses typed demo records; REST or SSE can occupy the same seam later.">
    <section className="docs-layout"><div className="docs-contract-list"><div className="directory-section-heading"><div><p className="eyebrow">Typed models / source map</p><h2>Data contracts in the open.</h2></div><span className="mono muted">07 MODELS</span></div>{contracts.map((contract) => <div className="contract-row" key={contract.name}><div className="contract-icon"><Braces size={15} /></div><div><h3>{contract.name}</h3><p>{contract.role}</p></div><span className="contract-source mono">{contract.source}</span></div>)}</div><aside className="docs-adapter glass-panel"><p className="eyebrow">Adapter boundary</p><h2>demoApi</h2><p>One read path today. A replaceable seam tomorrow.</p><div className="adapter-code"><span>GET /runs/:state</span><span>→ getRun(state)</span><span>→ HedgeRun</span></div><div className="adapter-status"><span className="green-dot" /> REST / SSE READY</div><Link href="/control-room" className="overview-cta">Open the control room <ArrowUpRight size={14} /></Link></aside></section>
  </DirectoryShell>;
}

export function AuditReceipts() {
  const run = getHedgeRun("completed");
  return <DirectoryShell active="audit" eyebrow="Audit logs / receipts" title="A decision trace, not a black box." lede="Follow the same events the operator sees in the control room. This view separates concise system logs from private reasoning and makes order status impossible to misread.">
    <section className="audit-grid"><div className="glass-panel audit-panel"><div className="directory-section-heading"><div><p className="eyebrow">Run events / completed sample</p><h2>Decision trace</h2></div><span className="mono muted">{run.events.length} EVENTS</span></div><div className="audit-events">{run.events.map((event) => <div className="audit-event" key={event.id}><div className={`timeline-marker timeline-${event.tone}`}><span /></div><div className="audit-event-time mono">{event.time}</div><div><strong>{event.actor}</strong><span className="timeline-state">{event.state}</span><p>{event.message}</p><small>{event.source}</small></div></div>)}</div></div><div className="glass-panel audit-panel"><div className="directory-section-heading"><div><p className="eyebrow">Execution receipts</p><h2>What actually happened?</h2></div><TerminalSquare size={17} /></div><div className="audit-receipts">{run.receipts.map((receipt) => <div className={`audit-receipt receipt-${receipt.status}`} key={receipt.id}><div className="audit-receipt-top"><span><CircleDot size={12} /> {receipt.status}</span><span className="mono">{receipt.executionId}</span></div><strong>{receipt.label}</strong><p>{receipt.detail}</p></div>)}</div><div className="audit-note"><Server size={15} /><span>Read-only demo. Execution IDs are mock records, not broker confirmations.</span></div></div></section>
  </DirectoryShell>;
}
