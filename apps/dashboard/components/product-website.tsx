"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";

const installTabs = ["mac", "windows", "linux"];
const macDownloadUrl = "https://github.com/zw124/mia-agent/releases/download/v0.1.0/Mia-0.1.0-arm64.dmg";
const featureRows = [
  ["01", "desktop first", "Mia launches as a real app. The agent service, dashboard, and local runtime are started for the user."],
  ["02", "tool execution", "Browser tasks, computer observation, clicks, typing, and key presses are shown as readable execution events."],
  ["03", "memory context", "Recent sessions and durable memories are loaded before routing, so follow-up questions stay grounded."],
  ["04", "agent room", "A visual operating room reflects the active run state instead of acting like a static decoration."],
];

function ProductTerminal() {
  return (
    <div className="opencode-product-terminal" aria-label="Mia product trace preview">
      <div className="terminal-message active">
        <span className="terminal-bar" />
        <p>open wikipedia, search algebra, click the first result</p>
        <small>kai</small>
      </div>
      <div className="terminal-response">
        <p>I’ll route this through the local computer-use worker.</p>
        <ul>
          <li>message_classifier <span>tool_task</span></li>
          <li>browser_task <span>wikipedia · algebra</span></li>
          <li>computer_observe <span>Safari frontmost</span></li>
          <li>click_screen <span>first result</span></li>
        </ul>
      </div>
      <div className="terminal-response muted">
        <p>done in 4.2s · 6 tool events</p>
      </div>
    </div>
  );
}

export function ProductWebsite() {
  const [isElectron, setIsElectron] = useState(false);

  useEffect(() => {
    setIsElectron(typeof (window as any).miaDesktop?.isElectron === "boolean");
  }, []);

  return (
    <main className={`opencode-site opencode-product-v2 ${isElectron ? "is-electron" : ""}`}>
      {isElectron ? <div className="electron-titlebar" /> : null}

      <div className="oc-page-frame">
        <header className="oc-nav">
          <a className="oc-wordmark" href="/" aria-label="Mia home">mia</a>
          <nav aria-label="Product navigation">
            <a href="#docs">Docs</a>
            <a href="#agent">Agent</a>
            <a href="/app">App</a>
          </nav>
          <a className="oc-download" href={macDownloadUrl}>
            <Download size={18} />
            Download
          </a>
        </header>

        <section className="oc-hero">
          <p className="oc-announcement">
            <span>New</span>
            Desktop app available for local agent runs. <a href="/app">Launch now</a>
          </p>

          <h1>The personal AI agent for your computer</h1>
          <p className="oc-subtitle">
            Mia is a desktop-first agent runtime with chat, memory, computer use, visible tool traces, and an agent room that reflects real work.
          </p>

          <div className="oc-install-card">
            <div className="oc-install-tabs">
              {installTabs.map((tab, index) => (
                <button key={tab} className={index === 0 ? "active" : ""} type="button">{tab}</button>
              ))}
            </div>
            <div className="oc-install-command">
              <span>open</span>
              <strong>/app</strong>
              <button type="button" aria-label="Copy launch command">⌘</button>
            </div>
          </div>
        </section>

        <ProductTerminal />

        <section id="agent" className="oc-section">
          <div className="oc-section-head">
            <span>agent runtime</span>
            <h2>Not a terminal demo. A product users can open.</h2>
          </div>
          <div className="oc-feature-list">
            {featureRows.map(([id, title, text]) => (
              <article key={id} className="oc-feature-row">
                <span>{id}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="docs" className="oc-final">
          <div>
            <span>ship mia</span>
            <h2>Sign in. Ask. Watch the work happen.</h2>
          </div>
          <div className="oc-final-actions">
            <a href={macDownloadUrl}>Download app</a>
            <a href="/app">Open web app</a>
          </div>
        </section>
      </div>
    </main>
  );
}
