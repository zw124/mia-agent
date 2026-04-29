"use client";

import {
  Activity,
  BellRing,
  Bot,
  Brain,
  Cable,
  CalendarClock,
  CircleDot,
  Clipboard,
  Clock3,
  DatabaseZap,
  ExternalLink,
  GitBranch,
  Inbox,
  KeyRound,
  LayoutDashboard,
  MessageSquareText,
  Radio,
  Search,
  Server,
  ShieldAlert,
  Sparkles,
  Terminal,
  Workflow,
} from "lucide-react";
import type { ComponentType, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "../../../convex/_generated/api";

type Section =
  | "dashboard"
  | "agents"
  | "memory"
  | "automations"
  | "events"
  | "consolidation"
  | "connectors";

type ThoughtLog = {
  _id: string;
  runId?: string;
  node: string;
  content: string;
  activeAgent?: string;
  createdAt: number;
};

type Message = {
  _id: string;
  direction: "inbound" | "outbound";
  messageHandle: string;
  content: string;
  fromNumber?: string;
  toNumber?: string;
  status?: string;
  createdAt: number;
};

type Memory = {
  _id: string;
  tier: "short_term" | "long_term" | "permanent";
  segment: string;
  status: "active" | "merged" | "deleted" | "manual_review";
  content: string;
  importanceScore: number;
  decayRate: number;
  updatedAt: number;
};

type AgentRun = {
  _id: string;
  runId: string;
  messageHandle?: string;
  activeAgent?: string;
  status: "running" | "completed" | "failed";
  startedAt: number;
  completedAt?: number;
  error?: string;
};

type AgentSpawn = {
  _id: string;
  runId: string;
  messageHandle: string;
  parentAgent: string;
  name: string;
  objective: string;
  allowedTools: string[];
  status: "planned" | "running" | "completed" | "failed" | "blocked";
  result?: string;
  error?: string;
  createdAt: number;
  updatedAt: number;
};

type CourtRun = {
  _id: string;
  runId: string;
  localDate: string;
  status: "running" | "completed" | "failed";
  startedAt: number;
  completedAt?: number;
  error?: string;
};

type CourtDecision = {
  _id: string;
  runId: string;
  action: "delete" | "merge" | "keep" | "manual_review";
  reason: string;
  memoryIds: string[];
  createdAt: number;
};

type PendingAction = {
  _id: string;
  kind: string;
  summary: string;
  risk: "safe" | "approval_required" | "manual_only";
  status: "pending" | "approved" | "completed" | "failed" | "expired";
  createdAt: number;
  expiresAt: number;
  result?: string;
  error?: string;
};

type WebhookEvent = {
  _id: string;
  messageHandle?: string;
  ignored: boolean;
  createdAt: number;
};

const navItems: { id: Section; label: string; icon: ComponentType<{ size?: number }> }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "automations", label: "Automations", icon: Workflow },
  { id: "events", label: "Events", icon: Activity },
  { id: "consolidation", label: "Consolidation", icon: GitBranch },
  { id: "connectors", label: "Connectors", icon: Cable },
];

function timeLabel(value?: number) {
  if (!value) return "pending";
  return new Intl.DateTimeFormat("en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortId(value = "") {
  return value.length > 10 ? `${value.slice(0, 6)}...${value.slice(-4)}` : value;
}

function EmptyState({ title }: { title: string }) {
  return <div className="empty-state">{title}</div>;
}

function LoadingRows() {
  return (
    <div className="loading-list" aria-label="Loading">
      <span />
      <span />
      <span />
    </div>
  );
}

function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function StatusLine({ label, ok, action }: { label: string; ok: boolean; action?: ReactNode }) {
  return (
    <div className="status-line">
      <span>{label}</span>
      <strong>{ok ? "Ready" : "Missing"}</strong>
      {action}
    </div>
  );
}

function Panel({
  title,
  icon: Icon,
  children,
  className = "",
}: {
  title: string;
  icon: ComponentType<{ size?: number }>;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-title">
        <Icon size={16} />
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function SetupInput({
  label,
  value,
  onChange,
  placeholder,
  secret = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  secret?: boolean;
}) {
  return (
    <label className="setup-field">
      <span>{label}</span>
      <input
        type={secret ? "password" : "text"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
    </label>
  );
}

function OnboardingExperience({ onFinish }: { onFinish: () => void }) {
  const [step, setStep] = useState(0);
  const [termsScrolled, setTermsScrolled] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [repositoryOpened, setRepositoryOpened] = useState(false);
  const [setupStatus, setSetupStatus] = useState<Record<string, boolean | string> | null>(null);
  const [setupSaved, setSetupSaved] = useState(false);
  const [setupError, setSetupError] = useState("");
  const [installing, setInstalling] = useState(false);
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState("https://api.openai.com/v1");
  const [modelName, setModelName] = useState("");
  const [convexUrl, setConvexUrl] = useState("");
  const [convexSiteUrl, setConvexSiteUrl] = useState("");
  const [agentUrl, setAgentUrl] = useState("http://localhost:8000");
  const [sendblueKeyId, setSendblueKeyId] = useState("");
  const [sendblueSecret, setSendblueSecret] = useState("");
  const [sendblueNumber, setSendblueNumber] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [ownerPhone, setOwnerPhone] = useState("");
  const [searxngUrl, setSearxngUrl] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch("/api/setup/status")
      .then((response) => response.json())
      .then((data) => setSetupStatus(data))
      .catch(() => setSetupStatus(null));
  }, []);

  const envText = [
    `OPENAI_API_KEY=${openaiKey}`,
    `OPENAI_BASE_URL=${openaiBaseUrl}`,
    `MODEL_NAME=${modelName}`,
    "",
    `CONVEX_URL=${convexUrl}`,
    `CONVEX_SITE_URL=${convexSiteUrl}`,
    `NEXT_PUBLIC_CONVEX_URL=${convexUrl}`,
    `AGENT_SERVICE_URL=${agentUrl}`,
    "MIA_INTERNAL_SECRET=change-me",
    "",
    `SENDBLUE_API_KEY_ID=${sendblueKeyId}`,
    `SENDBLUE_API_SECRET_KEY=${sendblueSecret}`,
    `SENDBLUE_FROM_NUMBER=${sendblueNumber}`,
    `SENDBLUE_WEBHOOK_SECRET=${webhookSecret}`,
    `SENDBLUE_STATUS_CALLBACK=${agentUrl}`,
    `OWNER_PHONE_NUMBER=${ownerPhone}`,
    `SEARXNG_BASE_URL=${searxngUrl}`,
  ].join("\n");

  async function copyEnv() {
    await navigator.clipboard.writeText(envText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  async function saveSetup() {
    setSetupError("");
    const response = await fetch("/api/setup/apply", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ envText, convexUrl }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      setSetupError(data.error ?? "Save failed");
      return;
    }
    setSetupSaved(true);
  }

  async function installDependencies() {
    setInstalling(true);
    await fetch("/api/setup/install-dependencies", { method: "POST" });
    const response = await fetch("/api/setup/status");
    setSetupStatus(await response.json());
    setInstalling(false);
  }

  const steps = [
    {
      navLabel: "Welcome",
      eyebrow: "Welcome",
      title: "Mia Agent",
      body: "Welcome. This guide will connect the pieces Mia needs before opening the dashboard.",
      icon: Sparkles,
      content: (
        <div className="welcome-logo-block">
          <img src="/mia-logo.png" alt="Mia Agent logo" />
          <p className="quiet-note">No account details are submitted from this screen.</p>
        </div>
      ),
    },
    {
      navLabel: "Terms",
      eyebrow: "Agreement",
      title: "Before Mia runs.",
      body: "Read this once. Mia can connect to local files, terminal commands, browser actions, iMessage, and external APIs when you configure those tools.",
      icon: ShieldAlert,
      content: (
        <div className="terms-block">
          <div
            className="terms-scroll"
            onScroll={(event) => {
              const target = event.currentTarget;
              const atBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 8;
              if (atBottom) setTermsScrolled(true);
            }}
          >
            <p>
              Mia is designed to act as a local personal agent. It can receive iMessages, call an
              OpenAI-compatible model, write operational records to Convex, create sub-agents, and
              use tools that you enable. Some tools are harmless, such as reading dashboard state.
              Other tools can affect your computer or external services.
            </p>
            <p>
              Owner-only tools include opening URLs, reading files, writing files, deleting files,
              opening applications, and running terminal commands. Risky actions are routed through
              the approval queue unless they are explicitly safe. You are responsible for the API
              keys, phone numbers, model endpoints, webhooks, and local paths you configure.
            </p>
            <p>
              This onboarding screen can write environment values to local project files when you
              press Save. It does not send those values to a third-party service from the browser.
              The services you configure later, such as SendBlue, Convex, SearXNG, and your model
              provider, will receive data according to the tools and endpoints you activate.
            </p>
            <p>
              Keep secrets private. Rotate any key that was pasted into chat, screenshots, shared
              logs, or public repositories. Do not enable terminal or file actions unless this Mac is
              yours and you understand the impact. Continue only if you want Mia to become the local
              control surface for this project.
            </p>
          </div>
          <label className="terms-check">
            <input
              type="checkbox"
              checked={termsAccepted}
              disabled={!termsScrolled}
              onChange={(event) => setTermsAccepted(event.target.checked)}
            />
            <span>{termsScrolled ? "I understand and agree." : "Scroll to the end to continue."}</span>
          </label>
        </div>
      ),
    },
    {
      navLabel: "GitHub",
      eyebrow: "Community",
      title: "Star the repository.",
      body: "Mia is open source. Star the repository on GitHub to show your support and help the project grow.",
      icon: ExternalLink,
      content: (
        <div className="link-stack">
          <div className="link-row">
            <a
              href="https://github.com/zhiliao000-star/mia-agent"
              target="_blank"
              rel="noreferrer"
              onClick={() => setRepositoryOpened(true)}
            >
            Star on GitHub <ExternalLink size={14} />
            </a>
          </div>
          <p className="quiet-note">
            {repositoryOpened ? "Repository opened. You can continue." : "Open the repository link to continue."}
          </p>
        </div>
      ),
    },
    {
      navLabel: "Intelligence",
      eyebrow: "Step 1",
      title: "Connect intelligence.",
      body: "Use any OpenAI-compatible endpoint. Mia only needs a key, base URL, and model name.",
      icon: KeyRound,
      content: (
        <div className="setup-grid">
          <SetupInput label="OPENAI_API_KEY" value={openaiKey} onChange={setOpenaiKey} placeholder="sk-..." secret />
          <SetupInput label="OPENAI_BASE_URL" value={openaiBaseUrl} onChange={setOpenaiBaseUrl} placeholder="https://api.openai.com/v1" />
          <SetupInput label="MODEL_NAME" value={modelName} onChange={setModelName} placeholder="gpt-4o-mini" />
        </div>
      ),
    },
    {
      navLabel: "Convex",
      eyebrow: "Step 2",
      title: "Create the source of truth.",
      body: "Open Convex, start the dev deployment, then copy your cloud URL and site URL.",
      icon: DatabaseZap,
      content: (
        <>
          <StatusLine
            label="Convex package"
            ok={Boolean(setupStatus?.convexInstalled)}
            action={!setupStatus?.convexInstalled ? (
              <button type="button" className="inline-button" onClick={installDependencies} disabled={installing}>
                {installing ? "Installing" : "Install"}
              </button>
            ) : null}
          />
          <div className="link-row">
            <a href="https://dashboard.convex.dev/" target="_blank" rel="noreferrer">
              Open Convex <ExternalLink size={14} />
            </a>
            <code>npx convex dev</code>
          </div>
          <div className="setup-grid two">
            <SetupInput label="CONVEX_URL" value={convexUrl} onChange={setConvexUrl} placeholder="https://...convex.cloud" />
            <SetupInput label="CONVEX_SITE_URL" value={convexSiteUrl} onChange={setConvexSiteUrl} placeholder="https://...convex.site" />
          </div>
        </>
      ),
    },
    {
      navLabel: "iMessage",
      eyebrow: "Step 3",
      title: "Wire iMessage.",
      body: "Open SendBlue, create API keys, choose your iMessage number, and set the inbound webhook.",
      icon: MessageSquareText,
      content: (
        <>
          <div className="link-row">
            <a href="https://app.sendblue.com/" target="_blank" rel="noreferrer">
              Open SendBlue <ExternalLink size={14} />
            </a>
            <code>{`${agentUrl.replace(/\/$/, "")}/webhooks/sendblue/receive`}</code>
          </div>
          <div className="setup-grid">
            <SetupInput label="SENDBLUE_API_KEY_ID" value={sendblueKeyId} onChange={setSendblueKeyId} placeholder="key id" secret />
            <SetupInput label="SENDBLUE_API_SECRET_KEY" value={sendblueSecret} onChange={setSendblueSecret} placeholder="secret" secret />
            <SetupInput label="SENDBLUE_FROM_NUMBER" value={sendblueNumber} onChange={setSendblueNumber} placeholder="+1645..." />
            <SetupInput label="SENDBLUE_WEBHOOK_SECRET" value={webhookSecret} onChange={setWebhookSecret} placeholder="webhook secret" secret />
          </div>
        </>
      ),
    },
    {
      navLabel: "Gateway",
      eyebrow: "Step 4",
      title: "Run the gateway.",
      body: "One process starts Convex, FastAPI, and the dashboard. Use ngrok when SendBlue needs a public URL.",
      icon: Server,
      content: (
        <>
          <StatusLine label="Gateway script" ok={Boolean(setupStatus?.gatewayInstalled)} />
          <div className="command-block">
            <code>npm run mia:gateway</code>
            <code>npm run mia:gateway:ngrok</code>
            <code>npm run mia:gateway:install</code>
          </div>
          <div className="setup-grid two">
            <SetupInput label="AGENT_SERVICE_URL" value={agentUrl} onChange={setAgentUrl} placeholder="http://localhost:8000" />
            <SetupInput label="OWNER_PHONE_NUMBER" value={ownerPhone} onChange={setOwnerPhone} placeholder="+1202..." />
          </div>
        </>
      ),
    },
    {
      navLabel: "Search",
      eyebrow: "Step 5",
      title: "Add search.",
      body: "Optional. Add a SearXNG base URL to unlock Mia's web_search tool.",
      icon: Search,
      content: (
        <SetupInput label="SEARXNG_BASE_URL" value={searxngUrl} onChange={setSearxngUrl} placeholder="https://searxng.example.com" />
      ),
    },
    {
      navLabel: "Environment",
      eyebrow: "Final",
      title: "Copy the environment.",
      body: "Paste this into your env files. Rotate any real secret that was pasted into chat or screenshots.",
      icon: Clipboard,
      content: (
        <>
          <pre className="env-preview">{envText}</pre>
          {setupError ? <p className="setup-error">{setupError}</p> : null}
          {setupSaved ? <p className="setup-ok">Saved to local env files.</p> : null}
          <button type="button" className="copy-button" onClick={saveSetup}>
            Save setup
          </button>
          <button type="button" className="copy-button" onClick={copyEnv}>
            {copied ? "Copied" : "Copy env"}
          </button>
        </>
      ),
    },
  ];

  const current = steps[step];
  const isLast = step === steps.length - 1;
  const cannotContinue = (step === 1 && (!termsScrolled || !termsAccepted)) || (step === 2 && !repositoryOpened);

  return (
    <main className="onboarding-stage">
      <section className="onboarding-shell">
        <aside className="onboarding-rail" aria-label="Onboarding steps">
          <div className="rail-brand">
            <img src="/mia-logo.png" alt="" />
            <div>
              <strong>Mia</strong>
              <span>Setup</span>
            </div>
          </div>
          <ol>
            {steps.map((item, index) => (
              <li key={item.title} className={index === step ? "active" : ""}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                {item.navLabel}
              </li>
            ))}
          </ol>
        </aside>

        <div key={step} className="onboarding-panel">
          <div className="onboarding-count">{String(step + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}</div>
          <p className="eyebrow">{current.eyebrow}</p>
          <h1>{current.title}</h1>
          <p className="onboarding-copy">{current.body}</p>
          <div className="onboarding-content">{current.content}</div>
          <div className="onboarding-footer">
            <div className="progress-line" aria-label="Onboarding progress">
              <span style={{ width: `${((step + 1) / steps.length) * 100}%` }} />
            </div>
            <div className="onboarding-actions">
              {step > 0 ? (
                <button type="button" className="ghost-button" onClick={() => setStep(step - 1)}>
                  Back
                </button>
              ) : null}
              <button
                type="button"
                className="next-button"
                disabled={cannotContinue}
                onClick={() => {
                  if (cannotContinue) return;
                  if (isLast) {
                    onFinish();
                  } else {
                    setStep(step + 1);
                  }
                }}
              >
                {isLast ? "Enter Dashboard" : step === 0 ? "Begin" : "Next"}
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export function MiaDashboard() {
  const [onboarded, setOnboarded] = useState(false);
  if (!onboarded) {
    return <OnboardingExperience onFinish={() => setOnboarded(true)} />;
  }

  return <DashboardApp />;
}

function DashboardApp() {
  const [section, setSection] = useState<Section>("dashboard");
  const thoughts = useQuery(api.thoughtLogs.recent, { limit: 80 }) as ThoughtLog[] | undefined;
  const activeAgent = useQuery(api.agentRuns.active, {}) as string | null | undefined;
  const agentRuns = useQuery(api.agentRuns.recent, { limit: 24 }) as AgentRun[] | undefined;
  const agentSpawns = useQuery(api.agentSpawns.recent, { limit: 40 }) as AgentSpawn[] | undefined;
  const messages = useQuery(api.messages.recent, { limit: 30 }) as Message[] | undefined;
  const webhookEvents = useQuery(api.messages.recentWebhookEvents, { limit: 30 }) as WebhookEvent[] | undefined;
  const memories = useQuery(api.memories.list, { limit: 80 }) as Memory[] | undefined;
  const pendingActions = useQuery(api.pendingActions.recent, { limit: 30 }) as PendingAction[] | undefined;
  const courtRuns = useQuery(api.memoryCourt.recentRuns, { limit: 16 }) as CourtRun[] | undefined;
  const courtDecisions = useQuery(api.memoryCourt.recentDecisions, { limit: 30 }) as CourtDecision[] | undefined;

  const stats = useMemo(() => {
    const memoryRows = memories ?? [];
    const spawnRows = agentSpawns ?? [];
    const messageRows = messages ?? [];
    const pendingRows = pendingActions ?? [];
    return {
      messages: messageRows.length,
      memories: memoryRows.filter((memory) => memory.status === "active").length,
      agents: spawnRows.length,
      runningAgents: spawnRows.filter((agent) => agent.status === "running" || agent.status === "planned").length,
      approvals: pendingRows.filter((action) => action.status === "pending").length,
      failures: [
        ...spawnRows.filter((agent) => agent.status === "failed" || agent.status === "blocked"),
        ...(agentRuns ?? []).filter((run) => run.status === "failed"),
      ].length,
      short: memoryRows.filter((memory) => memory.tier === "short_term" && memory.status === "active").length,
      long: memoryRows.filter((memory) => memory.tier === "long_term" && memory.status === "active").length,
      permanent: memoryRows.filter((memory) => memory.tier === "permanent" && memory.status === "active").length,
      review: memoryRows.filter((memory) => memory.status === "manual_review").length,
    };
  }, [agentRuns, agentSpawns, memories, messages, pendingActions]);

  const latestSpawn = agentSpawns?.[0];
  const recentThoughts = thoughts?.slice(0, 12);
  const recentAgents = agentSpawns?.slice(0, 12);

  return (
    <main className="ops-layout">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/mia-logo.png" alt="" />
          <div>
            <strong>Mia</strong>
            <span>Agent OS</span>
          </div>
        </div>
        <nav aria-label="Mia sections">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                aria-current={section === item.id ? "page" : undefined}
                onClick={() => setSection(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Mia</p>
            <h1>{navItems.find((item) => item.id === section)?.label}</h1>
          </div>
          <div className="agent-pill">
            <Radio size={16} />
            <span>{activeAgent ?? "idle"}</span>
          </div>
        </header>

        {section === "dashboard" && (
          <>
            <section className="metrics" aria-label="System status">
              <article>
                <span>Messages</span>
                <strong>{stats.messages}</strong>
                <small>recent window</small>
              </article>
              <article>
                <span>Memories</span>
                <strong>{stats.memories}</strong>
                <small>{stats.short}s / {stats.long}l / {stats.permanent}p</small>
              </article>
              <article>
                <span>Agents Spawned</span>
                <strong>{stats.agents}</strong>
                <small>{stats.runningAgents} active or planned</small>
              </article>
              <article>
                <span>Approvals</span>
                <strong>{stats.approvals}</strong>
                <small>pending iMessage approve</small>
              </article>
              <article>
                <span>Failures</span>
                <strong>{stats.failures}</strong>
                <small>blocked or failed</small>
              </article>
            </section>
            <section className="dashboard-grid">
              <Panel title="Agent Activity" icon={Bot} className="span-2">
                {recentAgents === undefined ? <LoadingRows /> : <AgentSpawnList agents={recentAgents} />}
              </Panel>
              <Panel title="Current Sub-Agent" icon={Sparkles}>
                {latestSpawn ? (
                  <div className="focus-card">
                    <Badge tone={latestSpawn.status}>{latestSpawn.status}</Badge>
                    <h3>{latestSpawn.name}</h3>
                    <p>{latestSpawn.objective}</p>
                    <div className="tool-strip">
                      {latestSpawn.allowedTools.map((tool) => (
                        <Badge key={tool}>{tool}</Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <EmptyState title="No sub-agent spawned yet" />
                )}
              </Panel>
              <Panel title="Thought Stream" icon={CircleDot} className="span-2">
                {recentThoughts === undefined ? <LoadingRows /> : <ThoughtList thoughts={recentThoughts} />}
              </Panel>
              <Panel title="Approval Queue" icon={ShieldAlert}>
                {pendingActions === undefined ? <LoadingRows /> : <PendingActionList actions={pendingActions.slice(0, 8)} />}
              </Panel>
            </section>
          </>
        )}

        {section === "agents" && (
          <section className="dashboard-grid">
            <Panel title="Generated Sub-Agents" icon={Bot} className="span-2">
              {agentSpawns === undefined ? <LoadingRows /> : <AgentSpawnList agents={agentSpawns} detailed />}
            </Panel>
            <Panel title="Agent Runs" icon={Activity}>
              {agentRuns === undefined ? <LoadingRows /> : <AgentRunList runs={agentRuns} />}
            </Panel>
            <Panel title="Tool Allocation" icon={Terminal} className="span-3">
              {agentSpawns === undefined ? <LoadingRows /> : <ToolMatrix agents={agentSpawns} />}
            </Panel>
          </section>
        )}

        {section === "memory" && (
          <section className="dashboard-grid">
            <Panel title="Memory Inventory" icon={Brain} className="span-3">
              {memories === undefined ? <LoadingRows /> : <MemoryTable memories={memories} />}
            </Panel>
          </section>
        )}

        {section === "automations" && (
          <section className="dashboard-grid">
            <Panel title="Nightly Court Cron" icon={CalendarClock}>
              {courtRuns === undefined ? <LoadingRows /> : <CourtRunList runs={courtRuns} />}
            </Panel>
            <Panel title="Approval Required" icon={BellRing} className="span-2">
              {pendingActions === undefined ? <LoadingRows /> : <PendingActionList actions={pendingActions} detailed />}
            </Panel>
          </section>
        )}

        {section === "events" && (
          <section className="dashboard-grid">
            <Panel title="iMessage Traffic" icon={MessageSquareText} className="span-2">
              {messages === undefined ? <LoadingRows /> : <MessageList messages={messages} />}
            </Panel>
            <Panel title="Webhook Events" icon={Inbox}>
              {webhookEvents === undefined ? <LoadingRows /> : <WebhookList events={webhookEvents} />}
            </Panel>
            <Panel title="Thought Logs" icon={CircleDot} className="span-3">
              {thoughts === undefined ? <LoadingRows /> : <ThoughtList thoughts={thoughts} />}
            </Panel>
          </section>
        )}

        {section === "consolidation" && (
          <section className="dashboard-grid">
            <Panel title="Memory Court Runs" icon={DatabaseZap}>
              {courtRuns === undefined ? <LoadingRows /> : <CourtRunList runs={courtRuns} />}
            </Panel>
            <Panel title="Court Decisions" icon={GitBranch} className="span-2">
              {courtDecisions === undefined ? <LoadingRows /> : <CourtDecisionList decisions={courtDecisions} />}
            </Panel>
          </section>
        )}

        {section === "connectors" && (
          <section className="dashboard-grid">
            <Panel title="Connector Health" icon={Cable} className="span-3">
              <ConnectorGrid
                activeAgent={activeAgent}
                messages={messages}
                webhookEvents={webhookEvents}
                thoughts={thoughts}
                courtRuns={courtRuns}
              />
            </Panel>
          </section>
        )}
      </section>
    </main>
  );
}

function AgentSpawnList({ agents, detailed = false }: { agents: AgentSpawn[]; detailed?: boolean }) {
  if (agents.length === 0) return <EmptyState title="No generated sub-agents yet" />;
  return (
    <div className="agent-list">
      {agents.map((agent) => (
        <article key={agent._id} className="agent-row">
          <div className="row-head">
            <strong>{agent.name}</strong>
            <Badge tone={agent.status}>{agent.status}</Badge>
          </div>
          <p>{agent.objective}</p>
          <div className="meta-line">
            <span>{timeLabel(agent.createdAt)}</span>
            <span>run {shortId(agent.runId)}</span>
            <span>parent {agent.parentAgent}</span>
          </div>
          <div className="tool-strip">
            {agent.allowedTools.map((tool) => (
              <Badge key={`${agent._id}-${tool}`}>{tool}</Badge>
            ))}
          </div>
          {detailed && (agent.result || agent.error) ? (
            <pre>{agent.error ?? agent.result}</pre>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function AgentRunList({ runs }: { runs: AgentRun[] }) {
  if (runs.length === 0) return <EmptyState title="No agent runs yet" />;
  return (
    <div className="compact-list">
      {runs.map((run) => (
        <div key={run._id} className="compact-row">
          <Badge tone={run.status}>{run.status}</Badge>
          <strong>{run.activeAgent ?? "parent_router"}</strong>
          <span>{timeLabel(run.startedAt)}</span>
          <small>{shortId(run.runId)}</small>
        </div>
      ))}
    </div>
  );
}

function ToolMatrix({ agents }: { agents: AgentSpawn[] }) {
  const toolCounts = new Map<string, number>();
  for (const agent of agents) {
    for (const tool of agent.allowedTools) {
      toolCounts.set(tool, (toolCounts.get(tool) ?? 0) + 1);
    }
  }
  const rows = Array.from(toolCounts.entries()).sort((a, b) => b[1] - a[1]);
  if (rows.length === 0) return <EmptyState title="No tools allocated yet" />;
  const max = Math.max(...rows.map(([, count]) => count));
  return (
    <div className="tool-matrix">
      {rows.map(([tool, count]) => (
        <div key={tool} className="tool-meter">
          <span>{tool}</span>
          <div>
            <i style={{ width: `${(count / max) * 100}%` }} />
          </div>
          <strong>{count}</strong>
        </div>
      ))}
    </div>
  );
}

function ThoughtList({ thoughts }: { thoughts: ThoughtLog[] }) {
  if (thoughts.length === 0) return <EmptyState title="No thought logs yet" />;
  return (
    <div className="timeline">
      {thoughts.map((log) => (
        <div key={log._id} className="timeline-row">
          <time>{timeLabel(log.createdAt)}</time>
          <div>
            <strong>{log.node}</strong>
            <p>{log.content}</p>
          </div>
          <Badge>{log.activeAgent ?? "none"}</Badge>
        </div>
      ))}
    </div>
  );
}

function MemoryTable({ memories }: { memories: Memory[] }) {
  if (memories.length === 0) return <EmptyState title="No memories stored yet" />;
  return (
    <div className="memory-table">
      {memories.map((memory) => (
        <div key={memory._id} className="memory-row">
          <Badge tone={memory.tier}>{memory.tier}</Badge>
          <p>{memory.content}</p>
          <span>{memory.segment}</span>
          <span>{memory.status}</span>
          <meter min={0} max={1} value={memory.importanceScore} />
          <small>decay {memory.decayRate}</small>
        </div>
      ))}
    </div>
  );
}

function PendingActionList({ actions, detailed = false }: { actions: PendingAction[]; detailed?: boolean }) {
  if (actions.length === 0) return <EmptyState title="No approval-required actions" />;
  return (
    <div className="compact-list">
      {actions.map((action) => (
        <div key={action._id} className="approval-row">
          <div className="row-head">
            <strong>{action.kind}</strong>
            <Badge tone={action.status}>{action.status}</Badge>
          </div>
          <p>{action.summary}</p>
          <div className="meta-line">
            <span>{action.risk}</span>
            <span>expires {timeLabel(action.expiresAt)}</span>
          </div>
          {detailed && (action.result || action.error) ? <pre>{action.error ?? action.result}</pre> : null}
        </div>
      ))}
    </div>
  );
}

function MessageList({ messages }: { messages: Message[] }) {
  if (messages.length === 0) return <EmptyState title="No iMessages recorded" />;
  return (
    <div className="message-list">
      {messages.map((message) => (
        <div key={message._id} className="message-row">
          <Badge tone={message.direction}>{message.direction}</Badge>
          <p>{message.content}</p>
          <div className="meta-line">
            <span>{timeLabel(message.createdAt)}</span>
            <span>{shortId(message.messageHandle)}</span>
            <span>{message.status ?? "recorded"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function WebhookList({ events }: { events: WebhookEvent[] }) {
  if (events.length === 0) return <EmptyState title="No webhook events" />;
  return (
    <div className="compact-list">
      {events.map((event) => (
        <div key={event._id} className="compact-row">
          <Badge tone={event.ignored ? "blocked" : "completed"}>{event.ignored ? "ignored" : "accepted"}</Badge>
          <strong>{shortId(event.messageHandle ?? "no-handle")}</strong>
          <span>{timeLabel(event.createdAt)}</span>
        </div>
      ))}
    </div>
  );
}

function CourtRunList({ runs }: { runs: CourtRun[] }) {
  if (runs.length === 0) return <EmptyState title="No court runs yet" />;
  return (
    <div className="compact-list">
      {runs.map((run) => (
        <div key={run._id} className="compact-row">
          <Badge tone={run.status}>{run.status}</Badge>
          <strong>{run.localDate}</strong>
          <span>{timeLabel(run.startedAt)}</span>
          <small>{shortId(run.runId)}</small>
        </div>
      ))}
    </div>
  );
}

function CourtDecisionList({ decisions }: { decisions: CourtDecision[] }) {
  if (decisions.length === 0) return <EmptyState title="No consolidation decisions yet" />;
  return (
    <div className="court-stack">
      {decisions.map((decision) => (
        <article key={decision._id} className="decision">
          <div className="row-head">
            <Badge tone={decision.action}>{decision.action}</Badge>
            <span>{decision.memoryIds.length} memories</span>
          </div>
          <p>{decision.reason}</p>
          <small>{timeLabel(decision.createdAt)}</small>
        </article>
      ))}
    </div>
  );
}

function ConnectorGrid({
  activeAgent,
  messages,
  webhookEvents,
  thoughts,
  courtRuns,
}: {
  activeAgent: string | null | undefined;
  messages: Message[] | undefined;
  webhookEvents: WebhookEvent[] | undefined;
  thoughts: ThoughtLog[] | undefined;
  courtRuns: CourtRun[] | undefined;
}) {
  const connectors = [
    {
      name: "Convex",
      description: "Realtime source of truth",
      status: "connected",
      icon: DatabaseZap,
      detail: `${messages?.length ?? 0} recent messages`,
    },
    {
      name: "SendBlue",
      description: "iMessage inbound and outbound webhooks",
      status: webhookEvents && webhookEvents.length > 0 ? "connected" : "waiting",
      icon: MessageSquareText,
      detail: `${webhookEvents?.length ?? 0} webhook events`,
    },
    {
      name: "Agent Service",
      description: "FastAPI LangGraph runtime",
      status: activeAgent ? "connected" : "idle",
      icon: Bot,
      detail: activeAgent ?? "idle",
    },
    {
      name: "SearXNG",
      description: "Web search tool backend",
      status: thoughts?.some((thought) => thought.content.toLowerCase().includes("web_search")) ? "connected" : "ready",
      icon: Search,
      detail: "tool registered",
    },
    {
      name: "Memory Court",
      description: "Nightly consolidation cron",
      status: courtRuns?.[0]?.status ?? "waiting",
      icon: Clock3,
      detail: courtRuns?.[0]?.localDate ?? "no run yet",
    },
  ];
  return (
    <div className="connector-grid">
      {connectors.map((connector) => {
        const Icon = connector.icon;
        return (
          <article key={connector.name} className="connector-card">
            <Icon size={20} />
            <div>
              <div className="row-head">
                <strong>{connector.name}</strong>
                <Badge tone={connector.status}>{connector.status}</Badge>
              </div>
              <p>{connector.description}</p>
              <small>{connector.detail}</small>
            </div>
          </article>
        );
      })}
    </div>
  );
}
