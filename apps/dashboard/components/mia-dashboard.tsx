"use client";

import { useQuery, useMutation } from "convex/react";
import { api } from "../../../convex/_generated/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { 
  LogOut, 
  MessageSquare,
  Plus,
  Send, 
  Settings, 
  ChevronRight, 
  Compass, 
  Cpu, 
  CheckCircle2, 
  AlertCircle 
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

type SessionState = {
  loading: boolean;
  authenticated: boolean;
  hasRegisteredUsers: boolean;
  user?: { email: string; role: string };
};

type View = "chat" | "history" | "dashboard" | "settings" | "room";
type DashboardTab = "setup" | "channels" | "usage";

type SetupForm = {
  openaiApiKey: string;
  openaiBaseUrl: string;
  modelName: string;
  agentServiceUrl: string;
  sendblueApiKeyId: string;
  sendblueSecretKey: string;
  sendblueFromNumber: string;
  ownerPhoneNumber: string;
  telegramBotToken: string;
  telegramOwnerChatId: string;
  composioEnabled: boolean;
};

type DesktopState = {
  connected?: boolean;
  dashboardUrl?: string;
  lastGatewayStart?: number | null;
  windowBounds?: { x: number; y: number; width: number; height: number } | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  messageHandle?: string;
  linkedMessageHandle?: string;
  pending?: boolean;
};

type RoomAgent = {
  id: string;
  label: string;
  station: string;
  state: "rest" | "walk" | "work" | "blocked";
};

const defaultSetup: SetupForm = {
  openaiApiKey: "",
  openaiBaseUrl: "https://api.openai.com/v1",
  modelName: "gpt-4o-mini",
  agentServiceUrl: "http://localhost:8000",
  sendblueApiKeyId: "",
  sendblueSecretKey: "",
  sendblueFromNumber: "",
  ownerPhoneNumber: "",
  telegramBotToken: "",
  telegramOwnerChatId: "",
  composioEnabled: false,
};

async function loadSession(): Promise<SessionState> {
  const response = await fetch("/api/auth/session", { cache: "no-store" });
  const data = await response.json();
  return {
    loading: false,
    authenticated: Boolean(data.authenticated),
    hasRegisteredUsers: Boolean(data.hasRegisteredUsers),
    user: data.user,
  };
}

function ThinkingProcess({ 
  messageHandle, 
  isThinking,
}: { 
  messageHandle: string; 
  isThinking: boolean;
}) {
  const [expanded, setExpanded] = useState(isThinking);
  const thoughts = useQuery(api.thoughtLogs.byMessageHandle, { messageHandle });
  const timelineItems = thoughts ?? [];

  // Keep expanded if still actively thinking
  useEffect(() => {
    if (isThinking) {
      setExpanded(true);
    }
  }, [isThinking]);

  if (timelineItems.length === 0 && !isThinking) {
    return null;
  }

  return (
    <div className="thinking-container">
      <button 
        type="button"
        className={`thinking-header ${expanded ? "expanded" : ""}`} 
        onClick={() => setExpanded(!expanded)}
      >
        {isThinking ? (
          <span className="thinking-caret"><span className="thinking-loader" /></span>
        ) : (
          <span className="thinking-caret">
            <ChevronRight size={13} />
          </span>
        )}
        <span>
          {isThinking 
            ? "thinking" 
            : `completed (${timelineItems.length} steps)`}
        </span>
      </button>
      
      {expanded && (
        <div className="thinking-content">
          {timelineItems.length === 0 ? (
            <div className="thinking-live-note">
              <span className="thinking-pulse" />
              waiting for real agent events
            </div>
          ) : timelineItems.map((t: any, index: number) => {
            const isTool = String(t.node || "").startsWith("tool_call:");
            const isToolResult = String(t.node || "").startsWith("tool_result:");
            const isError = t.node === "error" || t.node === "failed";
            const rawToolName = String(t.node || "").replace(/^tool_(call|result):/, "");
            const isComputerAction = /computer|browser|click|type|press_key|scroll|open_url/.test(rawToolName);
            return (
              <div key={t._id || index} className={`thinking-step ${isTool || isToolResult ? "tool" : ""} ${isComputerAction ? "computer" : ""}`}>
                <span className={`thinking-step-bullet ${isError ? "error" : ""} ${isTool || isToolResult ? "tool" : ""}`} />
                <div className="thinking-step-info">
                  <span className="thinking-step-node">
                    {isComputerAction ? <span className="cursor-glyph" aria-hidden="true" /> : null}
                    {t.node}
                  </span>
                  <span className="thinking-step-text">{t.content}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Auth Screen ─── */
function AuthScreen({ onDone, hasRegisteredUsers }: { onDone: () => void; hasRegisteredUsers: boolean }) {
  const [mode, setMode] = useState<"login" | "register">(hasRegisteredUsers ? "login" : "register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const response = await fetch(mode === "login" ? "/api/auth/login" : "/api/auth/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await response.json();
    setBusy(false);
    if (!response.ok || !data.ok) {
      setError(data.error ?? "Something went wrong.");
      return;
    }
    onDone();
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-story">
          <div className="auth-art-frame">
            <a className="auth-brand" href="/">
              <img src="/mia-logo.png" alt="" />
              <span>Mia</span>
            </a>
            <div className="auth-art-center">
              <div className="auth-orb" />
              <p>Local agent runtime</p>
            </div>
            <div className="auth-terminal" aria-hidden="true">
              <div><span>$</span> mia auth status</div>
              <div className="muted">→ browser session required</div>
              <div><span>$</span> mia runtime</div>
              <div className="ok">✓ local agent ready</div>
            </div>
          </div>
        </div>
        <div className="auth-card">
          <a className="auth-back" href="/">← Back to site</a>
          <div>
            <p className="auth-card-label">Welcome to Mia</p>
            <h2>{mode === "login" ? "Sign in to your workspace" : "Create your workspace"}</h2>
            <p>
              {mode === "login"
                ? "Continue to chat, dashboard, memory, settings, and agent traces."
                : "Create the first owner account for this Mia workspace."}
            </p>
          </div>
          <form onSubmit={submit} className="auth-form">
            <label>
              Email
              <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" />
            </label>
            <label>
              Password
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="At least 6 characters" />
            </label>
            {error ? <div className="error-box">{error}</div> : null}
            <button className="primary-button auth-submit" type="submit" disabled={busy}>
              {busy ? "Checking..." : mode === "login" ? "Enter workspace" : "Create workspace"}
            </button>
            <button className="text-button auth-switch" type="button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Need an account? Register" : "Already registered? Log in"}
            </button>
          </form>
          <div className="auth-note">
            <span>Workspace includes</span>
            <ul>
              <li>Chat history and memory context</li>
              <li>Dashboard settings for local runtime</li>
              <li>Visible thinking and tool execution traces</li>
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function AgentRoomScreen() {
  const recentRuns = useQuery(api.agentRuns.recent, { limit: 3 });
  const recentThoughts = useQuery(api.thoughtLogs.recent, { limit: 18 });

  const roomState = useMemo(() => {
    const latestRun = recentRuns?.[0];
    const latestThought = recentThoughts?.[0];
    const isRunning = latestRun?.status === "running";
    const latestNode = String(latestThought?.node ?? "");
    const latestContent = String(latestThought?.content ?? "");
    const activityText = latestNode || latestRun?.activeAgent || "resting";
    const toolText = `${latestNode} ${latestContent}`.toLowerCase();
    const hasComputer = /computer|browser|click|type|press|scroll|open_url/.test(toolText);
    const hasMemory = /memory|context|remember/.test(toolText);
    const hasReview = /review|complete|result|final|failed|blocked|error/.test(toolText);
    const blocked = latestRun?.status === "failed" || /blocked|error|failed|permission|assistive/.test(toolText);

    const agents: RoomAgent[] = [
      {
        id: "mia",
        label: "Mia",
        station: "router desk",
        state: blocked ? "blocked" : isRunning ? "work" : "rest",
      },
      {
        id: "computer",
        label: "Computer",
        station: "browser station",
        state: blocked && hasComputer ? "blocked" : isRunning && hasComputer ? "work" : isRunning ? "walk" : "rest",
      },
      {
        id: "memory",
        label: "Memory",
        station: "archive",
        state: isRunning && hasMemory ? "work" : isRunning ? "walk" : "rest",
      },
      {
        id: "review",
        label: "Review",
        station: "output table",
        state: blocked ? "blocked" : isRunning && hasReview ? "work" : isRunning ? "walk" : "rest",
      },
    ];

    return {
      isRunning,
      blocked,
      activityText,
      agents,
    };
  }, [recentRuns, recentThoughts]);

  return (
    <section className="agent-room-screen">
      <div className="pixel-agents-frame">
        <iframe
          className="pixel-agents-iframe"
          src="/pixel-agents/index.html"
          title="Mia Agent Room"
          sandbox="allow-scripts allow-same-origin"
        />
        <div className={`agent-room-live-layer ${roomState.isRunning ? "is-running" : ""}`}>
          {roomState.agents.map((agent) => (
            <div key={agent.id} className={`room-live-agent ${agent.id} ${agent.state}`}>
              <span className="room-live-dot" />
              <span className="room-live-label">{agent.label}</span>
            </div>
          ))}
          <div className={`room-live-status ${roomState.blocked ? "blocked" : roomState.isRunning ? "working" : "resting"}`}>
            {roomState.blocked ? "blocked" : roomState.isRunning ? "working" : "resting"} · {roomState.activityText}
          </div>
        </div>
      </div>
    </section>
  );
}

function OnboardingOverlay({
  desktopState,
  onComplete,
}: {
  desktopState: DesktopState | null;
  onComplete: () => void;
}) {
  return (
    <div className="onboarding-overlay">
      <section className="onboarding-card">
        <p className="onboarding-kicker">First run</p>
        <h1>Mia is ready after sign in.</h1>
        <p className="onboarding-copy">
          The desktop app handles the local dashboard, realtime database, and agent service. You should not need a terminal for normal use.
        </p>
        <div className="onboarding-steps">
          <div className="onboarding-step done">
            <CheckCircle2 size={15} />
            <span>Account session active</span>
          </div>
          <div className={`onboarding-step ${desktopState?.connected ? "done" : "pending"}`}>
            <CheckCircle2 size={15} />
            <span>{desktopState?.connected ? "Desktop runtime connected" : "Desktop runtime will reconnect automatically"}</span>
          </div>
          <div className="onboarding-step done">
            <CheckCircle2 size={15} />
            <span>Chat, history, settings, and agent room are available</span>
          </div>
        </div>
        <button type="button" className="primary-button onboarding-action" onClick={onComplete}>
          Enter Mia
        </button>
      </section>
    </div>
  );
}

function ChatScreen({ 
  sessionId, 
  onUpdateTitle 
}: { 
  sessionId: string | null;
  onUpdateTitle?: (sessionId: string, title: string) => void;
}) {
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [sendError, setSendError] = useState("");
  const [sessionMessages, setSessionMessages] = useState<ChatMessage[]>([]);
  const [hasInitialized, setHasInitialized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const convexSessionMessages = useQuery(
    api.messages.bySession,
    sessionId ? { sessionId: sessionId as any } : "skip" as any,
  );

  // Convert Convex messages to ChatMessage format
  const convexMessages = useMemo(() => {
    if (!convexSessionMessages) return [];
    return convexSessionMessages.map((m: any): ChatMessage => ({
      id: m._id || m.messageHandle,
      role: m.direction === "inbound" ? "user" : "assistant",
      content: m.content,
      messageHandle: m.messageHandle,
      linkedMessageHandle: m.linkedMessageHandle,
    }));
  }, [convexSessionMessages]);

  useEffect(() => {
    setSessionMessages([]);
    setHasInitialized(false);
    setInput("");
    setThinking(false);
    setSendError("");
  }, [sessionId]);

  useEffect(() => {
    if (!hasInitialized && convexMessages.length > 0) {
      setSessionMessages(convexMessages);
      setHasInitialized(true);
    }
    if (!hasInitialized && convexSessionMessages !== undefined && convexMessages.length === 0) {
      setHasInitialized(true);
    }
  }, [convexMessages, convexSessionMessages, hasInitialized]);

  const messages = sessionMessages;
  const isEmptyState = messages.length === 0 && !thinking;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  async function sendMessage(text: string) {
    const message = text.trim();
    if (!message || thinking) return;
    const tempUserId = `web:${crypto.randomUUID()}`;
    const tempAssistantId = `assistant-${Date.now()}`;

    setThinking(true);
    setInput("");
    setSendError("");
    if (!hasInitialized) setHasInitialized(true);
    setSessionMessages((current) => [
      ...current,
      { id: tempUserId, role: "user", content: message, messageHandle: tempUserId },
      { id: tempAssistantId, role: "assistant", content: "", messageHandle: tempAssistantId, pending: true },
    ]);

    // Update session title on first message
    if (sessionMessages.length === 0 && sessionId && onUpdateTitle) {
      const title = message.length > 50 ? message.slice(0, 50) + "..." : message;
      onUpdateTitle(sessionId, title);
    }
    
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message, clientMessageHandle: tempUserId, sessionId }),
      });
      const data = await response.json();
      if (!data.ok) {
        setSessionMessages((current) =>
          current.map((entry) =>
            entry.id === tempAssistantId
              ? { ...entry, content: data.error ?? "Mia could not answer right now.", pending: false }
              : entry,
          ),
        );
        setSendError(data.error ?? "Mia could not answer right now.");
      } else {
        const reply = typeof data.reply === "string" ? data.reply.trim() : "";
        if (!reply) {
          setSessionMessages((current) => current.filter((entry) => entry.id !== tempAssistantId));
          setSendError("Mia returned an empty response.");
          return;
        }
        setSessionMessages((current) =>
          current.map((entry) =>
            entry.id === tempAssistantId
              ? {
                  ...entry,
                  linkedMessageHandle: data.messageHandle ?? tempUserId,
                  content: reply,
                  pending: false,
                }
              : entry,
          ),
        );
      }
    } catch {
      setSessionMessages((current) =>
        current.map((entry) =>
          entry.id === tempAssistantId
            ? { ...entry, content: "Could not reach the local agent service.", pending: false }
            : entry,
        ),
      );
      setSendError("Could not reach the local agent service.");
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="chat-main">
      <div className={`messages-area ${isEmptyState ? "is-empty" : ""}`}>
        {sendError ? (
          <div className="chat-alert">
            <AlertCircle size={15} />
            <span>{sendError}</span>
          </div>
        ) : null}
        {isEmptyState ? (
          <div className="empty-state">
            <h2>Message Mia</h2>
          </div>
        ) : (
          <>
            {messages.map((m: any, index: number) => {
              const isUser = m.role === "user";
              const isLatestAssistant = !isUser && index === messages.length - 1;

              return (
                <div key={m.id || index} className={`message-wrapper ${isUser ? "user" : "assistant"}`}>
                  <div className={`message ${isUser ? "user" : "assistant"}`}>
                    {m.content ? (
                      <div className="message-bubble">
                        {isUser ? m.content : <MarkdownMessage content={m.content} />}
                      </div>
                    ) : null}
                  </div>
                  {!isUser && m.messageHandle && (m.pending || isLatestAssistant) && (
                    <ThinkingProcess 
                      messageHandle={m.linkedMessageHandle || m.messageHandle} 
                      isThinking={isLatestAssistant && thinking} 
                    />
                  )}
                </div>
              );
            })}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className={`composer-area ${isEmptyState ? "is-empty" : ""}`}>
        <div className="composer-inner">
          <input
            className="composer-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder="Message Mia"
          />
          <button
            className="composer-send"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || thinking}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function HistoryScreen({ 
  sessions, 
  activeSessionId,
  onSelectSession 
}: { 
  sessions: any[]; 
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <div className="history-main">
      <div className="history-header">
        <div>
          <div className="chat-header-title">History</div>
          <div className="chat-header-sub">{sessions.length} sessions</div>
        </div>
      </div>

      <div className="history-list">
        {sessions.length === 0 ? (
          <div className="history-empty">No chat history yet.</div>
        ) : (
          sessions.map((session) => (
            <article
              key={session._id}
              className={`history-item clickable ${activeSessionId === session._id ? "active" : ""}`}
              onClick={() => onSelectSession(session._id)}
            >
              <div className="history-content">
                <div className="history-session-title">{session.title}</div>
                <div className="history-session-meta">{new Date(session.updatedAt ?? session.createdAt).toLocaleString()}</div>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

/* ─── Dashboard Admin View ─── */
function DashboardAdmin({ 
  form, 
  setForm, 
  onBack,
  isElectron,
  desktopState,
  refreshDesktopState,
  initialTab = "setup",
}: { 
  form: SetupForm; 
  setForm: (f: SetupForm) => void; 
  onBack: () => void; 
  isElectron: boolean;
  desktopState: DesktopState | null;
  refreshDesktopState: () => Promise<void>;
  initialTab?: DashboardTab;
}) {
  const [tab, setTab] = useState<DashboardTab>(initialTab);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [systemState, setSystemState] = useState<any>(null);

  async function loadSystemStatus() {
    try {
      const res = await fetch("/api/system/status");
      const data = await res.json();
      if (data.ok) {
        setSystemState(data);
      }
    } catch (err) {
      console.error("System status error", err);
    }
  }

  useEffect(() => {
    loadSystemStatus();
    const interval = setInterval(loadSystemStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);

  async function saveSetup() {
    setError("");
    setSaved(false);
    const envText = [
      `OPENAI_API_KEY=${form.openaiApiKey}`,
      `OPENAI_BASE_URL=${form.openaiBaseUrl}`,
      `MODEL_NAME=${form.modelName}`,
      "TRANSCRIPTION_MODEL=whisper-1",
      `AGENT_SERVICE_URL=${form.agentServiceUrl}`,
      "MIA_INTERNAL_SECRET=change-me",
      `SENDBLUE_API_KEY_ID=${form.sendblueApiKeyId}`,
      `SENDBLUE_API_SECRET_KEY=${form.sendblueSecretKey}`,
      `SENDBLUE_FROM_NUMBER=${form.sendblueFromNumber}`,
      "SENDBLUE_WEBHOOK_SECRET=",
      `OWNER_PHONE_NUMBER=${form.ownerPhoneNumber}`,
      `TELEGRAM_BOT_TOKEN=${form.telegramBotToken}`,
      "TELEGRAM_WEBHOOK_SECRET=",
      `TELEGRAM_OWNER_CHAT_ID=${form.telegramOwnerChatId}`,
      `TELEGRAM_ALLOWED_CHAT_IDS=${form.telegramOwnerChatId}`,
      `COMPOSIO_ENABLED=${form.composioEnabled ? "true" : "false"}`,
      "SEARXNG_BASE_URL=",
    ].join("\n");
    
    try {
      const response = await fetch("/api/setup/apply", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ envText }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        setError(data.error ?? "Could not save setup.");
        return;
      }
      setSaved(true);
      setTimeout(loadSystemStatus, 1500);
    } catch (err) {
      setError("Failed to reach setup API.");
    }
  }

  async function startDesktopGateway() {
    if (!(window as any).miaDesktop?.startGateway) return;
    await (window as any).miaDesktop.startGateway();
    await refreshDesktopState();
    setTimeout(loadSystemStatus, 1000);
  }

  async function stopDesktopGateway() {
    if (!(window as any).miaDesktop?.stopGateway) return;
    await (window as any).miaDesktop.stopGateway();
    await refreshDesktopState();
    setTimeout(loadSystemStatus, 1000);
  }

  function envFromForm() {
    return `OPENAI_API_KEY=${form.openaiApiKey}
OPENAI_BASE_URL=${form.openaiBaseUrl}
MODEL_NAME=${form.modelName}
AGENT_SERVICE_URL=${form.agentServiceUrl}
SENDBLUE_API_KEY_ID=${form.sendblueApiKeyId}
SENDBLUE_API_SECRET_KEY=${form.sendblueSecretKey}
SENDBLUE_FROM_NUMBER=${form.sendblueFromNumber}
OWNER_PHONE_NUMBER=${form.ownerPhoneNumber}
TELEGRAM_BOT_TOKEN=${form.telegramBotToken}
TELEGRAM_OWNER_CHAT_ID=${form.telegramOwnerChatId}
COMPOSIO_ENABLED=${form.composioEnabled ? "true" : "false"}`;
  }

  return (
    <div className="dashboard-admin">
      <div className="dashboard-admin-header">
        <div>
          <p style={{ fontSize: 11, color: "var(--app-accent)", fontWeight: 600, marginBottom: 4, textTransform: "uppercase" }}>Mia settings</p>
          <h1>{initialTab === "usage" ? "Dashboard" : "Settings"}</h1>
        </div>
        <button type="button" className="back-btn" onClick={onBack}>
          <MessageSquare size={14} style={{ marginRight: 4 }} /> Back to chat
        </button>
      </div>

      <div className="admin-tabs">
        {(["setup", "channels", "usage"] as const).map((t) => (
          <button 
            type="button"
            key={t} 
            className={`admin-tab ${tab === t ? "active" : ""}`} 
            onClick={() => setTab(t)}
          >
            {t === "setup" && <Settings size={13} />}
            {t === "channels" && <Compass size={13} />}
            {t === "usage" && <Cpu size={13} />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "setup" && (
        <div className="setup-card">
          <div>
            <h2>Model configuration</h2>
            <p style={{ marginTop: 4 }}>Connect an OpenAI-compatible large language model. Mia operates via standard local FastAPI routing.</p>
          </div>
          <div className="form-grid">
            <label>API Key<input type="password" value={form.openaiApiKey} onChange={(e) => setForm({ ...form, openaiApiKey: e.target.value })} placeholder="sk-..." /></label>
            <label>Model Name<input value={form.modelName} onChange={(e) => setForm({ ...form, modelName: e.target.value })} /></label>
            <label>Base URL<input value={form.openaiBaseUrl} onChange={(e) => setForm({ ...form, openaiBaseUrl: e.target.value })} /></label>
            <label>Agent URL<input value={form.agentServiceUrl} onChange={(e) => setForm({ ...form, agentServiceUrl: e.target.value })} /></label>
          </div>
          
          <h2 style={{ marginTop: 12 }}>External channels</h2>
          <div className="form-grid">
            <label>SendBlue API Key ID<input value={form.sendblueApiKeyId} onChange={(e) => setForm({ ...form, sendblueApiKeyId: e.target.value })} /></label>
            <label>SendBlue Secret<input type="password" value={form.sendblueSecretKey} onChange={(e) => setForm({ ...form, sendblueSecretKey: e.target.value })} /></label>
            <label>SendBlue From Number<input value={form.sendblueFromNumber} onChange={(e) => setForm({ ...form, sendblueFromNumber: e.target.value })} /></label>
            <label>Owner Phone Number<input value={form.ownerPhoneNumber} onChange={(e) => setForm({ ...form, ownerPhoneNumber: e.target.value })} /></label>
            <label>Telegram Bot Token<input type="password" value={form.telegramBotToken} onChange={(e) => setForm({ ...form, telegramBotToken: e.target.value })} /></label>
            <label>Telegram Owner Chat ID<input value={form.telegramOwnerChatId} onChange={(e) => setForm({ ...form, telegramOwnerChatId: e.target.value })} /></label>
          </div>
          
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 500, marginTop: 8 }}>
            <input type="checkbox" checked={form.composioEnabled} onChange={(e) => setForm({ ...form, composioEnabled: e.target.checked })} />
            Enable Composio connected-app integrations
          </label>
          
          {error ? <div className="error-box">{error}</div> : null}
          {saved ? <div className="success-box">Setup saved successfully.</div> : null}
          
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button type="button" className="primary-button" onClick={saveSetup}>Save configurations</button>
          </div>
        </div>
      )}

      {tab === "channels" && (
        <div className="admin-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          <div className="admin-card">
            <h3>Message relay</h3>
            <p>Connect SendBlue only if you want Mia to receive messages outside the desktop app.</p>
            <span style={{ 
              fontSize: 12, 
              color: form.sendblueApiKeyId ? "var(--success)" : "var(--text-tertiary)", 
              fontWeight: 500, 
              marginTop: 12, 
              display: "flex", 
              alignItems: "center", 
              gap: 4 
            }}>
              {form.sendblueApiKeyId ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              {form.sendblueApiKeyId ? "SendBlue Configured" : "Awaiting settings setup"}
            </span>
          </div>
          <div className="admin-card">
            <h3>Telegram relay</h3>
            <p>Paste bot token and owner chat ID only if you want a secondary chat surface.</p>
            <span style={{ 
              fontSize: 12, 
              color: form.telegramBotToken ? "var(--success)" : "var(--text-tertiary)", 
              fontWeight: 500, 
              marginTop: 12, 
              display: "flex", 
              alignItems: "center", 
              gap: 4 
            }}>
              {form.telegramBotToken ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              {form.telegramBotToken ? "Telegram Configured" : "Awaiting settings setup"}
            </span>
          </div>
          <div className="admin-card">
            <h3>Composio Apps</h3>
            <p>Connect third party services: Gmail, GitHub, Slack, etc. Executions are permission-approval gated.</p>
            <span style={{ 
              fontSize: 12, 
              color: form.composioEnabled ? "var(--success)" : "var(--text-tertiary)", 
              fontWeight: 500, 
              marginTop: 12, 
              display: "flex", 
              alignItems: "center", 
              gap: 4 
            }}>
              {form.composioEnabled ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              {form.composioEnabled ? "Composio active" : "Optional connection"}
            </span>
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div className="admin-grid" style={{ gap: 24 }}>
          <div className="admin-card">
            <h3>Local Gateway Engine Status</h3>
            <p>Mia runs the local dashboard, data sync, Python agent service, and optional network tunnels.</p>
            
            <div className="health-status-bar" style={{ marginTop: 12 }}>
              {systemState?.services?.map((svc: any) => (
                <div key={svc.id} className="health-status-badge">
                  <span className={`indicator ${svc.status === 'online' || svc.status === 'ready' ? '' : 'offline'}`} />
                  <strong>{svc.name}:</strong> 
                  <span style={{ color: "var(--text-secondary)" }}>{svc.status}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="admin-card">
            <h3>Active Runs & heartbeats</h3>
            <p>Realtime heartbeat, recovery status, and the last time Mia confirmed the local runtime is healthy.</p>
            <div style={{ background: "var(--surface-subtle)", borderRadius: 6, padding: 12, marginTop: 8, fontSize: 13 }}>
              <strong>Last heartbeat update:</strong> {systemState?.heartbeat ? new Date(systemState.heartbeat.completedAt).toLocaleString() : "Waiting for heartbeat..."}<br/>
              <strong>Gateway Status:</strong> <span style={{ color: systemState?.heartbeat?.status === "ok" ? "var(--success)" : "var(--text-tertiary)", fontWeight: 600 }}>{systemState?.heartbeat?.status || "disconnected"}</span>
            </div>
          </div>

          {isElectron ? (
            <div className="admin-card">
              <h3>Desktop companion</h3>
              <p>The desktop shell can start or stop the local gateway for you. This keeps Mia usable without managing terminals manually.</p>
              <div className="desktop-runtime-row">
                <span className={`indicator ${desktopState?.connected ? "" : "offline"}`} />
                <span>{desktopState?.connected ? "Gateway running" : "Gateway stopped"}</span>
              </div>
              <div className="desktop-runtime-actions">
                <button type="button" className="primary-button" onClick={startDesktopGateway}>Start local engine</button>
                <button type="button" className="secondary-button" onClick={stopDesktopGateway}>Stop engine</button>
              </div>
              {desktopState?.lastGatewayStart ? (
                <p className="desktop-runtime-meta">Last started {new Date(desktopState.lastGatewayStart).toLocaleString()}.</p>
              ) : null}
            </div>
          ) : null}
        </div>
      )}

      <div className="admin-card" style={{ marginTop: 8 }}>
        <h3>Environment Variables preview</h3>
        <pre className="env-preview-block">{envFromForm()}</pre>
      </div>
    </div>
  );
}

/* ─── Main Dashboard ─── */
export function MiaDashboard() {
  const [isElectron, setIsElectron] = useState(false);
  const [desktopState, setDesktopState] = useState<DesktopState | null>(null);
  const [session, setSession] = useState<SessionState>({ loading: true, authenticated: false, hasRegisteredUsers: false });
  const [view, setView] = useState<View>("chat");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [form, setForm] = useState<SetupForm>(defaultSetup);
  const [showOnboarding, setShowOnboarding] = useState(false);
  
  const createSession = useMutation(api.sessions.create);
  const updateTitleMutation = useMutation(api.sessions.updateTitle);
  const sessionsList = useQuery(api.sessions.list);
  const [creatingSession, setCreatingSession] = useState(false);

  useEffect(() => {
    if (!session.authenticated || sessionsList === undefined || creatingSession) {
      return;
    }

    if (currentSessionId) {
      const stillExists = sessionsList.some((session) => session._id === currentSessionId);
      if (!stillExists) {
        setCurrentSessionId(sessionsList[0]?._id ?? null);
      }
      return;
    }

    if (sessionsList.length > 0) {
      setCurrentSessionId(sessionsList[0]._id);
      return;
    }

    setCreatingSession(true);
    createSession({ title: "New Chat" })
      .then((id) => {
        setCurrentSessionId(id as any);
      })
      .finally(() => {
        setCreatingSession(false);
      });
  }, [session.authenticated, sessionsList, currentSessionId, creatingSession, createSession]);

  async function startNewChat() {
    setCreatingSession(true);
    try {
      const id = await createSession({ title: "New Chat" });
      setCurrentSessionId(id as any);
      setView("chat");
    } finally {
      setCreatingSession(false);
    }
  }

  function handleSelectSession(sessionId: string) {
    setCurrentSessionId(sessionId);
    setView("chat");
  }

  function handleUpdateTitle(sessionId: string, title: string) {
    updateTitleMutation({ sessionId: sessionId as any, title });
  }

  async function refreshSession() {
    setSession(await loadSession());
  }

  async function loadConfig() {
    try {
      const res = await fetch("/api/setup/status");
      const data = await res.json();
      if (data.ok && data.config) {
        setForm(data.config);
      }
    } catch (err) {
      console.error("Config fetch error", err);
    }
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    await refreshSession();
  }

  async function refreshDesktopState() {
    const stateApi = (window as any).miaDesktop?.state;
    if (!stateApi) return;
    try {
      const state = await stateApi();
      setDesktopState(state);
    } catch (error) {
      console.error("Desktop state error", error);
    }
  }

  useEffect(() => {
    setIsElectron(typeof (window as any).miaDesktop?.isElectron === "boolean");
    refreshSession();
    loadConfig();
    refreshDesktopState();
  }, []);

  useEffect(() => {
    if (!session.authenticated) return;
    setShowOnboarding(localStorage.getItem("mia:onboarding:v1") !== "done");
  }, [session.authenticated]);

  function completeOnboarding() {
    localStorage.setItem("mia:onboarding:v1", "done");
    setShowOnboarding(false);
  }

  if (session.loading) return <main className="loading-screen">Loading Mia…</main>;
  if (!session.authenticated) return <AuthScreen hasRegisteredUsers={session.hasRegisteredUsers} onDone={refreshSession} />;

  return (
    <>
      {isElectron && <div className="electron-titlebar" />}
      <div className={`app-shell ${isElectron ? "is-electron" : ""}`} style={isElectron ? { paddingTop: 38 } : undefined}>
        <header className="app-topbar">
          <div className="topbar-left">
            <button type="button" className="topbar-new-chat" title="New chat" onClick={startNewChat}>
              <Plus size={15} />
            </button>
            <div className="topbar-identity">
              <span>Mia</span>
              <small>{session.user?.email}</small>
            </div>
          </div>

          <nav className="topbar-tabs" aria-label="Mia navigation">
            {([
              ["chat", "Chat"],
              ["history", "History"],
              ["dashboard", "Dashboard"],
              ["settings", "Settings"],
              ["room", "Agent Room"],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`topbar-tab ${view === id ? "active" : ""}`}
                onClick={() => setView(id)}
              >
                {label}
              </button>
            ))}
          </nav>

          <button type="button" className="topbar-logout" onClick={logout}>
            <LogOut size={13} />
            Log out
          </button>
        </header>

        <main className="app-content">
          <section className={`view-panel ${view === "chat" ? "is-active" : ""}`}>
            {currentSessionId ? (
              <ChatScreen sessionId={currentSessionId} onUpdateTitle={handleUpdateTitle} />
            ) : (
              <div className="loading-screen">Initializing chat...</div>
            )}
          </section>
          <section className={`view-panel ${view === "history" ? "is-active" : ""}`}>
            <HistoryScreen
              sessions={sessionsList ?? []}
              activeSessionId={currentSessionId}
              onSelectSession={handleSelectSession}
            />
          </section>
          <section className={`view-panel ${view === "room" ? "is-active" : ""}`}>
            <AgentRoomScreen />
          </section>
          <section className={`view-panel ${view === "dashboard" || view === "settings" ? "is-active" : ""}`}>
            <DashboardAdmin 
              form={form} 
              setForm={setForm} 
              onBack={() => setView("chat")}
              isElectron={isElectron}
              desktopState={desktopState}
              refreshDesktopState={refreshDesktopState}
              initialTab={view === "dashboard" ? "usage" : "setup"}
            />
          </section>
        </main>
      </div>
      {showOnboarding ? (
        <OnboardingOverlay desktopState={desktopState} onComplete={completeOnboarding} />
      ) : null}
    </>
  );
}
