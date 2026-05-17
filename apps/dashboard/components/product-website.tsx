"use client";

import { ArrowRight, Download, Hexagon } from "lucide-react";

export function ProductWebsite() {
  return (
    <main className="site">
      <header className="site-nav">
        <a className="site-brand" href="/">
          <Hexagon size={24} fill="currentColor" />
          <span>MIA</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#product">Product</a>
          <a href="#enterprise">Enterprise</a>
          <a href="#pricing">Pricing</a>
          <a href="#resources">Resources</a>
        </nav>
        <div className="site-actions">
          <a href="/app">Sign in</a>
          <a className="outline" href="mailto:sales@mia.local">Contact sales</a>
          <a className="solid" href="/app">Download</a>
        </div>
      </header>

      <section className="hero" id="product">
        <h1>
          Built to make you extraordinarily productive,
          <br />
          Mia is the best way to control AI.
        </h1>
        <div className="hero-actions">
          <a className="primary" href="/app">
            Download for macOS <Download size={19} />
          </a>
          <a className="secondary" href="mailto:sales@mia.local">
            Request a demo <ArrowRight size={19} />
          </a>
        </div>
      </section>

      <section className="product-shot" aria-label="Mia desktop preview">
        <div className="shot-backdrop">
          <div className="desktop-frame">
            <div className="window-bar">
              <span />
              <span />
              <span />
              <strong>Mia Desktop</strong>
            </div>
            <div className="desktop-grid">
              <aside className="desktop-list">
                <p>READY TO REVIEW 6</p>
                {[
                  ["Build landing page", "Done. Fonts preload in the head", "now"],
                  ["Analyze browser session", "All set. Workflow connected", "now"],
                  ["Plan computer control", "+20 -3 Drafted implementation", "10m"],
                  ["Set up iMessage", "Webhook and approval policy", "30m"],
                  ["Connect storage", "+135 -21 Convex state", "45m"],
                ].map(([title, detail, time]) => (
                  <div className="review-row" key={title}>
                    <i>✓</i>
                    <span>
                      <strong>{title}</strong>
                      <small>{detail}</small>
                    </span>
                    <em>{time}</em>
                  </div>
                ))}
              </aside>
              <section className="desktop-chat">
                <h2>Build local agent</h2>
                <div className="prompt">make Mia run from web, desktop, and iMessage</div>
                <p className="trace">Read README.md</p>
                <p className="trace">Read apps/agent-service/mia/main.py</p>
                <p className="trace">Thought 6s</p>
                <p className="answer">
                  I&apos;ll create a minimal product flow where the website explains the app and
                  the desktop client opens directly to chat.
                </p>
                <div className="file-change">apps/dashboard/app/page.tsx <b>+52 -0</b></div>
                <div className="file-change">apps/desktop/src/main.mjs <b>+18 -0</b></div>
              </section>
              <section className="desktop-preview">
                <div className="browser-bar">
                  <span>←</span>
                  <span>→</span>
                  <span>↻</span>
                  <strong>http://localhost:3000</strong>
                </div>
                <article>
                  <h3>Mia</h3>
                  <p>
                    A local AI agent for your computer. One login, one app, three ways to talk:
                    web, desktop, and iMessage.
                  </p>
                  <button>Open chat</button>
                </article>
              </section>
              <div className="cli-card">
                <div>connects local control:</div>
                <code>mia gateway start</code>
                <p>I&apos;ll keep the app running and ask before risky actions.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="site-section">
        <h2>One app after install.</h2>
        <p>
          The website explains and downloads Mia. The desktop app is the product: log in once,
          finish setup, and chat with the same agent from the app, browser, or iMessage.
        </p>
      </section>
    </main>
  );
}
