/* Obsidian Sentinel / primary control-room page: watchful, exacting, composed, and optimized for a 30-second read. */

import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  Command,
  Crosshair,
  Gauge,
  GitBranch,
  Hexagon,
  Layers3,
  Loader2,
  Play,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  ShieldX,
  Sparkles,
  TriangleAlert,
  Wifi,
  X,
  Zap,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

const HeroFluidCanvas = lazy(() => import("@/components/HeroFluidCanvas"));
import DirectoryChrome from "@/components/DirectoryChrome";
import { ASSET_URLS } from "@/lib/assets";
import { demoApi } from "@/lib/demoApi";
import {
  getHedgeRun,
  RUN_STATE_INDEX,
} from "@/demo/mockData";
import type {
  ExecutionReceipt,
  HedgeBid,
  HedgeRun,
  RiskCheck,
  RunEvent,
  RunState,
  StressScenario,
} from "@/demo/models";
import { RUN_STATES } from "@/demo/models";

const stateMeta: Record<RunState, { label: string; short: string; tone: string; description: string }> = {
  idle: { label: "Idle", short: "IDLE", tone: "neutral", description: "Ready for a new hedge run" },
  loading_portfolio: { label: "Loading portfolio", short: "LOAD", tone: "active", description: "Snapshot ingestion in progress" },
  stress_testing: { label: "Stress testing", short: "SHOCK", tone: "active", description: "Scenario paths are being computed" },
  collecting_bids: { label: "Collecting bids", short: "BIDS", tone: "active", description: "Auction window is open" },
  judging: { label: "Judging", short: "JUDGE", tone: "active", description: "Risk Governor is ranking structures" },
  risk_rejected: { label: "Risk rejected", short: "BLOCK", tone: "danger", description: "Policy gate blocked the proposal" },
  approved: { label: "Approved", short: "PASS", tone: "positive", description: "Selected hedge cleared policy" },
  dry_run_complete: { label: "Dry-run complete", short: "DRY", tone: "positive", description: "Simulation matched the order" },
  paper_order_submitted: { label: "Paper order submitted", short: "PAPER", tone: "active", description: "Order staged for venue routing" },
  completed: { label: "Completed", short: "DONE", tone: "positive", description: "Protection state is active" },
  reauction_required: { label: "Re-auction required", short: "RE-AUC", tone: "warning", description: "Inputs moved; refresh the auction" },
  failed: { label: "Failed", short: "FAIL", tone: "danger", description: "Execution halted safely" },
};

const replayStates = RUN_STATES;

function formatStateLabel(state: RunState) {
  return stateMeta[state].label;
}

function ControlButton({
  children,
  onClick,
  variant = "ghost",
  disabled = false,
  className = "",
}: {
  children: React.ReactNode;
  onClick: () => void;
  variant?: "ghost" | "primary" | "danger";
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      disabled={disabled}
      onClick={onClick}
      className={`control-button control-button-${variant} ${className}`}
    >
      {children}
    </Button>
  );
}

function PanelHeader({
  eyebrow,
  title,
  meta,
  icon,
}: {
  eyebrow: string;
  title: string;
  meta?: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="panel-header">
      <div className="panel-title-group">
        <div className="panel-icon">{icon}</div>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      {meta && <span className="panel-meta">{meta}</span>}
    </div>
  );
}

function StatusPill({ state, compact = false }: { state: RunState; compact?: boolean }) {
  const meta = stateMeta[state];
  return (
    <span className={`status-pill status-${meta.tone} ${compact ? "status-pill-compact" : ""}`}>
      <span className="status-dot" />
      {compact ? meta.short : meta.label}
    </span>
  );
}

function LoadingLines({ count = 3 }: { count?: number }) {
  return (
    <div className="loading-lines" aria-label="Loading">
      {Array.from({ length: count }).map((_, index) => <span key={index} className="skeleton-line" style={{ width: `${78 - index * 14}%` }} />)}
    </div>
  );
}

function MetricCard({
  label,
  value,
  suffix,
  detail,
  accent = false,
}: {
  label: string;
  value: string;
  suffix?: string;
  detail: string;
  accent?: boolean;
}) {
  return (
    <div className={`metric-card ${accent ? "metric-card-accent" : ""}`}>
      <p className="metric-label">{label}</p>
      <div className="metric-value-row">
        <span className="metric-value">{value}</span>
        {suffix && <span className="metric-suffix">{suffix}</span>}
      </div>
      <p className="metric-detail">{detail}</p>
    </div>
  );
}

function StateRail({ state, onSelect }: { state: RunState; onSelect: (state: RunState) => void }) {
  return (
    <section className="state-rail-panel glass-panel" aria-label="Run state controller">
      <div className="state-rail-heading">
        <div>
          <p className="eyebrow">Run state controller</p>
          <p className="rail-caption"><strong>12 states</strong> · replay the full protection cycle</p>
        </div>
        <div className="rail-current"><span className="rail-current-label">CURRENT</span><StatusPill state={state} /></div>
      </div>
      <div className="state-rail" role="list">
        {replayStates.map((item, index) => {
          const isCurrent = item === state;
          const isPast = RUN_STATE_INDEX[item] < RUN_STATE_INDEX[state];
          return (
            <button
              type="button"
              role="listitem"
              key={item}
              onClick={() => onSelect(item)}
              className={`state-step ${isCurrent ? "state-step-current" : ""} ${isPast ? "state-step-past" : ""}`}
              aria-label={`Jump to ${formatStateLabel(item)}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <span className="state-step-index">{String(index + 1).padStart(2, "0")}</span>
              <span className="state-step-name">{stateMeta[item].short}</span>
              {index < replayStates.length - 1 && <span className="state-step-connector" />}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function EdgeBanner({ state }: { state: RunState }) {
  if (state === "reauction_required") {
    return <div className="edge-banner edge-banner-warning"><TriangleAlert size={16} /><div><strong>Re-auction required</strong><span>Underlying book moved 2.1%. Updated inputs initiated a new auction cycle before any order can be routed.</span></div><span className="edge-banner-tag">INPUTS CHANGED</span></div>;
  }
  if (state === "risk_rejected") {
    return <div className="edge-banner edge-banner-danger"><ShieldX size={16} /><div><strong>Risk gate blocked the hedge</strong><span>Premium budget is above the active ceiling. No live order was sent; adjust the band and replay.</span></div><span className="edge-banner-tag">NO ORDER SENT</span></div>;
  }
  if (state === "failed") {
    return <div className="edge-banner edge-banner-danger"><X size={16} /><div><strong>Run failed safely</strong><span>Venue acknowledgement timed out. The run is halted and the paper order remains unconfirmed.</span></div><span className="edge-banner-tag">SAFE HALT</span></div>;
  }
  return null;
}

function HeroSnapshot({ run, loading }: { run: HedgeRun; loading: boolean }) {
  const { portfolio } = run;
  return (
    <div className="snapshot-card glass-panel">
      <div className="snapshot-topline"><span className="eyebrow">Portfolio risk snapshot</span><span className="snapshot-time"><Clock3 size={12} /> {portfolio.asOf}</span></div>
      <div className="snapshot-name-row"><h2>{portfolio.portfolioName}</h2><span className={`protection-badge protection-${portfolio.protectionState}`}><span className="status-dot" />{portfolio.protectionLabel}</span></div>
      <div className="metric-grid">
        {loading ? <div className="snapshot-skeleton"><LoadingLines count={4} /></div> : <>
          <MetricCard label="Equity" value={portfolio.equity} detail="NAV · base currency USD" accent />
          <MetricCard label="Drawdown" value={portfolio.drawdownPct.toFixed(1)} suffix="%" detail="from high-water mark" />
          <MetricCard label="Exposure" value={portfolio.exposurePct.toFixed(1)} suffix="%" detail="gross · current book" />
          <MetricCard label="Concentration" value={portfolio.concentrationPct.toFixed(1)} suffix="%" detail="top 10 positions" />
        </>}
      </div>
      <div className="snapshot-bottomline"><span><span className="green-dot" /> Protection loop is observable end-to-end</span><span className="mono muted">RUN ID / {run.runId}</span></div>
    </div>
  );
}

function ShadowBook({ run }: { run: HedgeRun }) {
  return (
    <div className="shadow-card glass-panel">
      <div className="shadow-title-row"><div><p className="eyebrow">Shadow book comparator</p><h2>Protection delta</h2></div><span className="delta-badge"><ArrowDownRight size={15} />−5.9 pp</span></div>
      <p className="shadow-note">Same stress paths. One book carries the selected hedge structure; one remains unprotected.</p>
      <div className="comparison-head"><span>SCENARIO OUTPUT</span><span>UNPROTECTED</span><span>PROTECTED</span></div>
      <div className="comparison-list">
        {run.shadowComparison.map((row) => (
          <div className="comparison-row" key={row.label}>
            <span className="comparison-label">{row.label}</span>
            <span className="comparison-number comparison-unprotected">{row.unprotected}</span>
            <span className="comparison-number comparison-protected">{row.protected}</span>
          </div>
        ))}
      </div>
      <div className="shadow-footer"><span className="footer-key"><span className="key-line key-lilac" /> Unprotected</span><span className="footer-key"><span className="key-line key-green" /> Protected</span><span className="mono muted">DELTA IS NOT A RETURN</span></div>
    </div>
  );
}

function ShockLab({ scenarios, loading }: { scenarios: StressScenario[]; loading: boolean }) {
  return (
    <section className="glass-panel dashboard-panel panel-shock">
      <PanelHeader eyebrow="01 / shock lab" title="Stress scenarios" meta="4 paths" icon={<Crosshair size={16} />} />
      <p className="panel-description">Loss estimates run against the current portfolio snapshot. Severity is relative to the active policy set.</p>
      {loading && <LoadingLines count={2} />}
      <div className="scenario-list">
        {scenarios.map((scenario, index) => (
          <div className="scenario-row" key={scenario.id}>
            <div className={`scenario-index scenario-${scenario.color}`}>{String(index + 1).padStart(2, "0")}</div>
            <div className="scenario-main"><strong>{scenario.name}</strong><span>{scenario.affectedPositions}</span></div>
            <span className={`severity-chip severity-${scenario.color}`}>{scenario.severity}</span>
            <span className="scenario-loss">{scenario.stressedLoss}</span>
          </div>
        ))}
      </div>
      <div className="panel-footer"><span><ScanLine size={13} /> Scenario engine / deterministic inputs</span><span className="mono">LAST RUN 14:32:04</span></div>
    </section>
  );
}

function HedgeAuction({ bids, state }: { bids: HedgeBid[]; state: RunState }) {
  const showLoading = state === "collecting_bids";
  return (
    <section className="glass-panel dashboard-panel panel-auction">
      <img className="panel-art-detail" src={ASSET_URLS.edgeDetail} alt="" aria-hidden="true" />
      <div className="panel-content-layer">
      <PanelHeader eyebrow="02 / hedge auction" title="Executable bids" meta="ranked by fit" icon={<GitBranch size={16} />} />
      <p className="panel-description">Candidate structures are normalized against premium, coverage band, and venue eligibility.</p>
      {showLoading && <LoadingLines count={2} />}
      <div className="bid-list">
        {bids.slice(0, 4).map((bid, index) => (
          <div className={`bid-row ${bid.selected && state !== "risk_rejected" ? "bid-selected" : ""}`} key={bid.id}>
            <div className="bid-rank">0{index + 1}</div>
            <div className="bid-main"><div className="bid-name-row"><strong>{bid.strategy}</strong>{bid.selected && <span className="selected-tag">SELECTED</span>}</div><span>{bid.source} · {bid.contractCount}</span></div>
            <div className="bid-metric"><span className="metric-label">PREMIUM</span><strong>{bid.premium}</strong></div>
            <div className="bid-metric protection-metric"><span className="metric-label">PROTECTION</span><strong>{bid.estimatedProtection}</strong></div>
            <div className="score-ring"><span>{bid.rankingScore.toFixed(1)}</span><small>SCORE</small></div>
          </div>
        ))}
      </div>
      <div className="panel-footer"><span><Sparkles size={13} /> Ranking score / 100</span><span className="mono">4 VENUES · 1 SELECTED</span></div>
      </div>
    </section>
  );
}

function RiskGovernor({ verdict }: { verdict: HedgeRun["riskVerdict"] }) {
  const isRejected = verdict.status === "rejected";
  const isPending = verdict.status === "pending";
  return (
    <section className={`glass-panel dashboard-panel panel-risk ${isRejected ? "panel-danger" : ""}`}>
      <PanelHeader eyebrow="03 / risk governor" title="Policy gate" meta="live ruleset" icon={<ShieldCheck size={16} />} />
      <div className={`verdict-card verdict-${verdict.status}`}>
        <div className="verdict-icon">{isRejected ? <ShieldX size={20} /> : isPending ? <Loader2 size={20} className="spin" /> : <ShieldCheck size={20} />}</div>
        <div><strong>{verdict.headline}</strong><span>{verdict.rationale}</span></div>
      </div>
      <div className="checklist">
        {verdict.checks.map((check) => <RiskCheckRow check={check} key={check.label} />)}
      </div>
      <div className="panel-footer"><span><Gauge size={13} /> 4 compliance checks</span><span className="mono">POLICY v2.8</span></div>
    </section>
  );
}

function RiskCheckRow({ check }: { check: RiskCheck }) {
  return <div className="check-row"><span className={`check-icon check-${check.status}`}>{check.status === "passed" ? <Check size={12} /> : check.status === "failed" ? <X size={12} /> : <CircleDot size={12} />}</span><div><strong>{check.label}</strong><span>{check.detail}</span></div><span className={`check-status check-status-${check.status}`}>{check.status}</span></div>;
}

function Timeline({ events }: { events: RunEvent[] }) {
  return (
    <section className="glass-panel dashboard-panel panel-timeline">
      <PanelHeader eyebrow="04 / agent event timeline" title="Decision trace" meta="no chain-of-thought" icon={<Layers3 size={16} />} />
      <p className="panel-description">Concise system events only. Every state transition is attributable to a source and timestamp.</p>
      <div className="timeline-list">
        {events.length === 0 ? <div className="empty-state"><CircleDot size={16} /><span>No events recorded yet.</span></div> : events.map((event) => <TimelineRow event={event} key={event.id} />)}
      </div>
    </section>
  );
}

function TimelineRow({ event }: { event: RunEvent }) {
  return (
    <div className="timeline-row">
      <div className={`timeline-marker timeline-${event.tone}`}><span /></div>
      <div className="timeline-time mono">{event.time}</div>
      <div className="timeline-copy"><div><strong>{event.actor}</strong><span className="timeline-state">{stateMeta[event.state].short}</span></div><p>{event.message}</p><span className="timeline-source">{event.source}</span></div>
      <ChevronRight size={14} className="timeline-chevron" />
    </div>
  );
}

function OrderReceipts({ receipts }: { receipts: ExecutionReceipt[] }) {
  const statusIcon = (status: ExecutionReceipt["status"]) => status === "filled" ? <Check size={14} /> : status === "rejected" || status === "failed" ? <X size={14} /> : status === "submitted" ? <ArrowUpRight size={14} /> : <Command size={14} />;
  return (
    <section className="glass-panel dashboard-panel panel-orders">
      <PanelHeader eyebrow="05 / order receipt" title="Execution states" meta="paper first" icon={<Zap size={16} />} />
      <p className="panel-description">Receipts are stateful records. A paper order is not a fill, and a failed run never implies execution.</p>
      {receipts.length === 0 ? <div className="empty-state empty-state-tall"><Command size={18} /><strong>No order receipts</strong><span>Start a replay to create a dry-run record.</span></div> : <div className="receipt-grid">{receipts.map((receipt) => <div className={`receipt-card receipt-${receipt.status}`} key={receipt.id}><div className="receipt-top"><span className="receipt-icon">{statusIcon(receipt.status)}</span><span className="receipt-status">{receipt.status}</span></div><strong>{receipt.label}</strong><span className="receipt-detail">{receipt.detail}</span><span className="receipt-id mono">{receipt.executionId}</span></div>)}</div>}
      <div className="panel-footer"><span><Wifi size={13} /> Broker link / simulated</span><span className="mono">READ-ONLY DEMO</span></div>
    </section>
  );
}

export default function Home() {
  const initialState = useMemo(() => {
    const requested = new URLSearchParams(window.location.search).get("state") as RunState | null;
    return requested && RUN_STATES.includes(requested) ? requested : "idle";
  }, []);
  const heroRef = useRef<HTMLElement | null>(null);
  const [state, setState] = useState<RunState>(initialState);
  const [run, setRun] = useState<HedgeRun>(() => getHedgeRun("idle"));
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    demoApi.getRun(state).then((snapshot) => {
      if (!cancelled) setRun(snapshot);
    });
    return () => { cancelled = true; };
  }, [state]);

  useEffect(() => {
    if (!isPlaying) return;
    if (state === "failed") {
      setIsPlaying(false);
      return;
    }
    const timeout = window.setTimeout(() => {
      const nextIndex = RUN_STATE_INDEX[state] + 1;
      if (nextIndex >= replayStates.length) {
        setIsPlaying(false);
      } else {
        setState(replayStates[nextIndex]);
      }
    }, 1200);
    return () => window.clearTimeout(timeout);
  }, [isPlaying, state]);

  const currentMeta = stateMeta[state];
  const loading = ["loading_portfolio", "stress_testing", "collecting_bids", "judging"].includes(state);
  const completionPct = useMemo(() => Math.round((RUN_STATE_INDEX[state] / (replayStates.length - 1)) * 100), [state]);

  const playReplay = () => {
    setState("idle");
    setIsPlaying(true);
  };
  const nextStep = () => {
    setIsPlaying(false);
    const nextIndex = RUN_STATE_INDEX[state] + 1;
    setState(nextIndex >= replayStates.length ? "idle" : replayStates[nextIndex]);
  };
  const reset = () => {
    setIsPlaying(false);
    setState("idle");
  };

  return (
    <main className="app-shell" style={{ "--progress": `${completionPct}%` } as React.CSSProperties}>
      <div className="atmosphere-layer" style={{ backgroundImage: `url(${ASSET_URLS.atmosphere})` }} />
      <div className="noise-layer" />
      <DirectoryChrome active="control-room" />

      <div className="page-frame">
        <StateRail state={state} onSelect={(next) => { setIsPlaying(false); setState(next); }} />

        <div className="control-strip">
          <div className="control-copy"><span className="control-kicker">RUNNER</span><span className="control-description">{currentMeta.description}</span><span className="control-progress"><span style={{ width: `${completionPct}%` }} /></span></div>
          <div className="control-actions">
            <ControlButton onClick={playReplay} variant="primary"><Play size={14} fill="currentColor" /> {isPlaying ? "Replaying" : "Play Replay"}</ControlButton>
            <ControlButton onClick={nextStep} disabled={state === "failed"}><ChevronRight size={15} /> Next Step</ControlButton>
            <ControlButton onClick={() => { setIsPlaying(false); setState("risk_rejected"); }} variant="danger"><ShieldX size={14} /> Simulate Risk Reject</ControlButton>
            <ControlButton onClick={() => { setIsPlaying(false); setState("reauction_required"); }}><GitBranch size={14} /> Trigger Re-Auction</ControlButton>
            <ControlButton onClick={reset}><RotateCcw size={14} /> Reset</ControlButton>
          </div>
        </div>

        <EdgeBanner state={state} />

        <section className="hero-grid" ref={heroRef}>
          <Suspense fallback={null}><HeroFluidCanvas hostRef={heroRef} /></Suspense>
          <div className="hero-copy">
            <div className="hero-kicker"><span className="kicker-line" /> OPERATING MODEL / 01</div>
            <h1>Protection is a<br /><em>state machine.</em></h1>
            <p className="hero-description">RaptorClick watches the portfolio, stress-tests the book, auctions executable protection, and only routes an order after the Risk Governor clears the path.</p>
            <div className="hero-explainer"><div className="explainer-icon"><Hexagon size={18} /></div><div><strong>See the full loop in under 30 seconds.</strong><span>Replay every gate, verdict, and receipt without losing the context around the book.</span></div></div>
            <div className="hero-footnote"><span className="mono">NORTHSTAR / GLOBAL MACRO</span><span><span className="green-dot" /> 186 POSITIONS MONITORED</span></div>
          </div>
          <div className="hero-art-stage">
            <div className="hero-art-grid" />
            <div className="hero-art-label label-top"><span className="mono">FIELD / LIVE LOOP</span><span className="label-rule" /></div>
            <div className="control-field-visual" aria-label="Live protection loop visualization">
              <div className="control-field-ring control-field-ring-one" />
              <div className="control-field-ring control-field-ring-two" />
              <div className="control-field-axis control-field-axis-x" />
              <div className="control-field-axis control-field-axis-y" />
              <div className="control-field-orbit control-field-orbit-one" />
              <div className="control-field-orbit control-field-orbit-two" />
              <div className="control-field-core"><span className="mono">RUN STATES</span><strong>12</strong><small>OBSERVABLE LOOP</small></div>
              <div className="control-field-sector sector-one"><span>01</span><strong>OBSERVE</strong></div>
              <div className="control-field-sector sector-two"><span>05</span><strong>JUDGE</strong></div>
              <div className="control-field-sector sector-three"><span>09</span><strong>PAPER</strong></div>
              <div className="control-field-sector sector-four"><span>12</span><strong>DONE</strong></div>
              <div className="control-field-readout"><span className="mono">ACTIVE PATH</span><strong>{currentMeta.short} / {completionPct}%</strong><small>Next gate is explicit.</small></div>
            </div>
          </div>
          <div className="hero-signal-card"><div className="signal-orbit" /><span className="mono signal-label">PROTECTIVE<br />DELTA</span><strong>−5.9 pp</strong><span className="signal-detail">peak drawdown<br />contained</span></div>
        </section>

        <section className="hero-data-grid"><HeroSnapshot run={run} loading={state === "loading_portfolio"} /><ShadowBook run={run} /></section>

        <div className="section-divider"><span className="eyebrow">SYSTEM OUTPUT</span><span className="divider-line" /><span className="mono muted">{currentMeta.short} / {completionPct}% COMPLETE</span></div>

        <section className="dashboard-grid">
          <ShockLab scenarios={run.scenarios} loading={state === "stress_testing"} />
          <HedgeAuction bids={run.bids} state={state} />
          <RiskGovernor verdict={run.riskVerdict} />
          <Timeline events={run.events} />
          <OrderReceipts receipts={run.receipts} />
        </section>

        <footer className="app-footer"><span><span className="green-dot" /> RaptorClick / protective intelligence layer</span><span className="mono">DEMO DATA · READ ONLY · v0.9.7</span><span className="mono">© 2026 RAPTORCLICK</span></footer>
      </div>
    </main>
  );
}
