"use client";

import {
  Check,
  ChevronRight,
  Command,
  Download,
  Key,
  LogOut,
  Monitor,
} from "lucide-react";
import { useEffect, useState } from "react";

type SessionState = {
  loading: boolean;
  authenticated: boolean;
  hasRegisteredUsers: boolean;
  user?: { email: string; role: string };
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

function LandingPage({ onLoginClick }: { onLoginClick: () => void }) {
  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', background: '#0a0a0a' }}>
      {/* Navigation */}
      <nav style={{ width: '100%', maxWidth: 1200, padding: '24px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
          <Command size={20} color="var(--strong)" />
          <span style={{ color: 'var(--strong)', fontSize: 16, fontWeight: 600, letterSpacing: '-0.02em', textTransform: 'uppercase' }}>Mia Agent</span>
        </div>
        
        <div style={{ display: 'flex', gap: 32, flex: 1, justifyContent: 'center' }}>
          {['Product', 'Enterprise', 'Pricing', 'Resources'].map(link => (
            <a key={link} href="#" style={{ color: 'var(--muted)', fontSize: 14, fontWeight: 500, transition: 'color 0.2s' }}>{link}</a>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1, justifyContent: 'flex-end' }}>
          <button onClick={onLoginClick} style={{ background: 'transparent', border: 'none', color: 'var(--strong)', fontSize: 14, fontWeight: 500 }}>
            Sign in
          </button>
          <button style={{ background: 'transparent', border: '1px solid var(--border-2)', color: 'var(--strong)', padding: '8px 16px', borderRadius: '100px', fontSize: 14, fontWeight: 500 }}>
            Contact sales
          </button>
          <button onClick={onLoginClick} style={{ background: 'var(--bg-inv)', color: 'var(--fg-inv)', border: 'none', padding: '8px 16px', borderRadius: '100px', fontSize: 14, fontWeight: 500 }}>
            Download
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ width: '100%', maxWidth: 1200, padding: '80px 32px 0', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        <h1 style={{ fontSize: 'clamp(40px, 5vw, 56px)', color: 'var(--strong)', fontWeight: 500, lineHeight: 1.15, letterSpacing: '-0.03em', marginBottom: 32, maxWidth: 800 }}>
          Built to make you extraordinarily productive,<br />
          Mia is the best way to work with AI.
        </h1>
        
        <div style={{ display: 'flex', gap: 16, marginBottom: 80 }}>
          <button 
            onClick={onLoginClick}
            style={{ background: 'var(--bg-inv)', color: 'var(--fg-inv)', border: 'none', padding: '14px 24px', borderRadius: '100px', fontSize: 16, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}
          >
            Download for macOS <Download size={18} />
          </button>
          <button 
            style={{ background: '#222222', color: 'var(--strong)', border: '1px solid transparent', padding: '14px 24px', borderRadius: '100px', fontSize: 16, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}
          >
            Request a demo <ChevronRight size={18} />
          </button>
        </div>

        {/* Mockup Placeholder */}
        <div style={{ width: '100%', height: 600, background: 'linear-gradient(180deg, #1c1c1c 0%, #111111 100%)', borderRadius: '16px 16px 0 0', border: '1px solid var(--border)', borderBottom: 'none', position: 'relative', overflow: 'hidden', display: 'flex', justifyContent: 'center', paddingTop: 40 }}>
           <div style={{ width: '90%', height: '100%', background: '#000', borderRadius: '8px 8px 0 0', border: '1px solid var(--border-2)', borderBottom: 'none', boxShadow: '0 -20px 60px rgba(0,0,0,0.5)' }}>
             <div style={{ height: 28, background: '#1a1a1a', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 6 }}>
               <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff5f56' }} />
               <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ffbd2e' }} />
               <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#27c93f' }} />
               <div style={{ flex: 1, textAlign: 'center', color: 'var(--muted)', fontSize: 11, fontFamily: 'monospace' }}>Mia Desktop</div>
             </div>
             <div style={{ padding: 24, display: 'flex', gap: 24, height: 'calc(100% - 28px)' }}>
               {/* Sidebar mockup */}
               <div style={{ width: 240, borderRight: '1px solid var(--border)' }}>
                 <div style={{ height: 16, width: 100, background: 'var(--border)', borderRadius: 4, marginBottom: 16 }} />
                 <div style={{ height: 12, width: 180, background: 'var(--border-2)', borderRadius: 4, marginBottom: 12 }} />
                 <div style={{ height: 12, width: 140, background: 'var(--border-2)', borderRadius: 4, marginBottom: 12 }} />
               </div>
               {/* Main mockup */}
               <div style={{ flex: 1 }}>
                 <div style={{ height: 24, width: 200, background: 'var(--border)', borderRadius: 4, marginBottom: 24 }} />
                 <div style={{ height: 12, width: '80%', background: 'var(--border-2)', borderRadius: 4, marginBottom: 12 }} />
                 <div style={{ height: 12, width: '60%', background: 'var(--border-2)', borderRadius: 4, marginBottom: 12 }} />
               </div>
             </div>
           </div>
        </div>
      </section>
    </main>
  );
}

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
    <main className="auth">
      <form className="auth-box" onSubmit={submit}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
          <div style={{ width: 48, height: 48, background: 'var(--panel-2)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--strong)', border: '1px solid var(--border)' }}>
            <Command size={24} />
          </div>
        </div>
        <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p>{mode === "login" ? "Enter your email to log in to your dashboard." : "Sign up to get access to the Mia desktop app."}</p>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <label>
            Email Address
            <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" placeholder="you@example.com" />
          </label>
          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>
        </div>

        {error ? <div style={{ color: 'var(--red)', fontSize: 13, background: 'rgba(239, 68, 68, 0.1)', padding: '10px 12px', borderRadius: '6px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>{error}</div> : null}
        
        <button type="submit" disabled={busy} style={{ marginTop: 8 }}>
          {busy ? "Please wait..." : mode === "login" ? "Continue with Email" : "Create Account"}
        </button>
        
        <button
          style={{ background: 'transparent', border: 'none', color: 'var(--muted)', fontSize: 13, marginTop: -8 }}
          type="button"
          onClick={() => {
            setError("");
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Log in"}
        </button>
      </form>
    </main>
  );
}

function DashboardScreen({ user, onLogout }: { user: { email: string }; onLogout: () => void }) {
  const [copied, setCopied] = useState(false);
  // Generate a random-looking sync code (in a real app, this would be fetched from the server)
  const syncCode = "839-421";

  return (
    <main style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', background: 'var(--bg)' }}>
      <header style={{ width: '100%', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '100%', maxWidth: 1000, padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 28, height: 28, background: 'var(--panel-2)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--strong)', border: '1px solid var(--border-2)' }}>
              <Command size={14} />
            </div>
            <span style={{ color: 'var(--strong)', fontSize: 14, fontWeight: 500 }}>Mia Dashboard</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ color: 'var(--muted)', fontSize: 13 }}>{user.email}</span>
            <button onClick={onLogout} style={{ background: 'transparent', border: 'none', color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </header>

      <div style={{ width: '100%', maxWidth: 1000, padding: '48px 24px', display: 'flex', flexDirection: 'column', gap: 40 }}>
        <div>
          <h1 style={{ fontSize: 32, color: 'var(--strong)', fontWeight: 600, letterSpacing: '-0.03em', marginBottom: 8 }}>Welcome aboard.</h1>
          <p style={{ color: 'var(--muted)', fontSize: 16 }}>Follow the steps below to connect your desktop app.</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24 }}>
          
          {/* Step 1 */}
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--panel)', padding: 32, display: 'flex', flexDirection: 'column' }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--panel-2)', border: '1px solid var(--border-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--strong)', marginBottom: 24 }}>
              1
            </div>
            <h2 style={{ fontSize: 18, color: 'var(--strong)', fontWeight: 500, marginBottom: 8 }}>Download the App</h2>
            <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6, marginBottom: 32, flex: 1 }}>
              Get the Mia desktop application for macOS. This app runs locally and manages your agent workflows.
            </p>
            <a 
              href="https://github.com/zhiliao000-star/mia-agent/releases"
              target="_blank"
              style={{ background: 'var(--bg-inv)', color: 'var(--fg-inv)', border: 'none', padding: '12px 16px', borderRadius: 'var(--radius-s)', fontSize: 14, fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%', textDecoration: 'none' }}
            >
              <Download size={16} /> Download for macOS
            </a>
          </div>

          {/* Step 2 */}
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--panel)', padding: 32, display: 'flex', flexDirection: 'column' }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--panel-2)', border: '1px solid var(--border-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--strong)', marginBottom: 24 }}>
              2
            </div>
            <h2 style={{ fontSize: 18, color: 'var(--strong)', fontWeight: 500, marginBottom: 8 }}>Authenticate</h2>
            <p style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
              Open the desktop app and paste this connection code to securely link your account.
            </p>
            
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border-2)', borderRadius: 'var(--radius-s)', padding: '24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, marginTop: 'auto' }}>
              <div style={{ fontSize: 32, letterSpacing: '0.1em', fontWeight: 600, color: 'var(--strong)', fontFamily: 'monospace' }}>
                {syncCode}
              </div>
              <button 
                onClick={() => {
                  navigator.clipboard.writeText(syncCode);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                style={{ background: 'var(--panel-2)', border: '1px solid var(--border)', color: 'var(--strong)', padding: '8px 16px', borderRadius: '100px', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {copied ? <Check size={14} color="var(--green)" /> : <Key size={14} />}
                {copied ? "Copied!" : "Copy Code"}
              </button>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}

export function MiaDashboard() {
  const [session, setSession] = useState<SessionState>({ loading: true, authenticated: false, hasRegisteredUsers: false });
  const [showLogin, setShowLogin] = useState(false);

  async function refreshSession() {
    setSession(await loadSession());
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    setShowLogin(false);
    await refreshSession();
  }

  useEffect(() => {
    refreshSession();
  }, []);

  if (session.loading) return <main className="auth"><div style={{ color: 'var(--muted)' }}>Loading...</div></main>;

  if (!session.authenticated) {
    if (showLogin || session.hasRegisteredUsers) {
      return <AuthScreen hasRegisteredUsers={session.hasRegisteredUsers} onDone={refreshSession} />;
    }
    return <LandingPage onLoginClick={() => setShowLogin(true)} />;
  }

  return <DashboardScreen user={session.user!} onLogout={logout} />;
}
