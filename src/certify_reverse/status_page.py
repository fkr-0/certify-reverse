from __future__ import annotations


def render_status_page(services_json: str, meta_json: str) -> str:
    """Render the self-contained operational dashboard HTML."""
    page = """<!doctype html>
<html lang="en" data-theme="system">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon">
  <link rel="icon" href="/favicon.ico" type="image/x-icon">
  <title>certify-reverse status</title>
  <style>
    :root {
      color-scheme: light dark;
      --page: #f5f7fb;
      --page-accent: #e8efff;
      --surface: #ffffff;
      --surface-raised: #ffffff;
      --surface-muted: #f4f6fa;
      --text: #172033;
      --text-muted: #5b6475;
      --border: #d8deea;
      --border-strong: #aeb8ca;
      --accent: #1957d2;
      --accent-hover: #1248b5;
      --accent-soft: #e8efff;
      --success: #087a41;
      --success-soft: #e6f6ed;
      --danger: #b42318;
      --danger-soft: #fdecea;
      --warning: #945f00;
      --warning-soft: #fff3d7;
      --focus: #ffbf47;
      --shadow: 0 18px 48px rgba(24, 39, 75, 0.09);
      --radius-lg: 20px;
      --radius-md: 12px;
      --radius-sm: 8px;
      --content: 1180px;
      --control-height: 44px;
    }

    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --page: #0e1420;
        --page-accent: #131d31;
        --surface: #151d2b;
        --surface-raised: #192334;
        --surface-muted: #202b3d;
        --text: #eef3fb;
        --text-muted: #aeb9ca;
        --border: #344156;
        --border-strong: #59677d;
        --accent: #8eb1ff;
        --accent-hover: #b3c9ff;
        --accent-soft: #24385f;
        --success: #69d69a;
        --success-soft: #173b2a;
        --danger: #ff938a;
        --danger-soft: #4c2425;
        --warning: #ffd078;
        --warning-soft: #49391d;
        --shadow: 0 20px 52px rgba(0, 0, 0, 0.3);
      }
    }

    :root[data-theme="dark"] {
      --page: #0e1420;
      --page-accent: #131d31;
      --surface: #151d2b;
      --surface-raised: #192334;
      --surface-muted: #202b3d;
      --text: #eef3fb;
      --text-muted: #aeb9ca;
      --border: #344156;
      --border-strong: #59677d;
      --accent: #8eb1ff;
      --accent-hover: #b3c9ff;
      --accent-soft: #24385f;
      --success: #69d69a;
      --success-soft: #173b2a;
      --danger: #ff938a;
      --danger-soft: #4c2425;
      --warning: #ffd078;
      --warning-soft: #49391d;
      --shadow: 0 20px 52px rgba(0, 0, 0, 0.3);
    }

    :root[data-theme="light"] {
      color-scheme: light;
    }

    *, *::before, *::after { box-sizing: border-box; }

    html {
      scroll-behavior: smooth;
      scroll-padding-top: 24px;
    }

    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.55;
      color: var(--text);
      background:
        radial-gradient(circle at 12% -10%, var(--page-accent), transparent 34rem),
        var(--page);
      text-rendering: optimizeLegibility;
    }

    a { color: var(--accent); text-underline-offset: 0.18em; }
    a:hover { color: var(--accent-hover); }

    button, input { font: inherit; }

    button, a, input, summary { -webkit-tap-highlight-color: transparent; }

    :focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 3px;
    }

    .skip-link {
      position: fixed;
      z-index: 100;
      top: 12px;
      left: 12px;
      transform: translateY(-160%);
      padding: 10px 14px;
      border-radius: var(--radius-sm);
      color: #111827;
      background: var(--focus);
      font-weight: 750;
      text-decoration: none;
      transition: transform 120ms ease;
    }

    .skip-link:focus { transform: translateY(0); }

    .shell {
      width: min(calc(100% - 32px), var(--content));
      margin-inline: auto;
    }

    .site-header { padding: 28px 0 18px; }

    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }

    .brand-mark {
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      width: 48px;
      height: 48px;
      border-radius: 14px;
      color: #ffffff;
      background: linear-gradient(145deg, #2867e8, #123f9d);
      box-shadow: 0 12px 30px rgba(25, 87, 210, 0.25);
      font-size: 14px;
      font-weight: 850;
      letter-spacing: 0.04em;
    }

    .eyebrow {
      margin: 0 0 2px;
      color: var(--text-muted);
      font-size: 0.78rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    h1, h2, h3, p { overflow-wrap: anywhere; }
    h1 { margin: 0; font-size: clamp(1.55rem, 3vw, 2.15rem); line-height: 1.15; }
    h2 { margin: 0; font-size: clamp(1.2rem, 2vw, 1.45rem); line-height: 1.25; }
    h3 { margin: 0; font-size: 1rem; line-height: 1.35; }

    .subtitle { margin: 5px 0 0; color: var(--text-muted); }

    .header-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
    }

    .section-nav {
      display: flex;
      gap: 6px;
      margin-top: 20px;
      padding: 5px;
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: color-mix(in srgb, var(--surface) 92%, transparent);
      box-shadow: 0 7px 20px rgba(24, 39, 75, 0.05);
      scrollbar-width: thin;
    }

    .section-nav a {
      display: inline-flex;
      align-items: center;
      min-height: var(--control-height);
      padding: 7px 12px;
      border-radius: 9px;
      color: var(--text-muted);
      font-size: 0.9rem;
      font-weight: 700;
      text-decoration: none;
      white-space: nowrap;
    }

    .section-nav a:hover { color: var(--text); background: var(--surface-muted); }

    main { padding: 6px 0 40px; }
    section { scroll-margin-top: 20px; }

    .stack { display: grid; gap: 18px; }

    .card {
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      background: color-mix(in srgb, var(--surface) 96%, transparent);
      box-shadow: var(--shadow);
    }

    .card-body { padding: clamp(18px, 3vw, 26px); }

    .overview-card {
      display: grid;
      gap: 22px;
      padding: clamp(20px, 4vw, 32px);
      background:
        linear-gradient(135deg, color-mix(in srgb, var(--accent-soft) 68%, var(--surface)), var(--surface) 60%);
    }

    .overview-heading {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
    }

    .overview-heading p { max-width: 72ch; margin: 8px 0 0; color: var(--text-muted); }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      min-height: 118px;
      padding: 16px;
      border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
      border-radius: var(--radius-md);
      background: color-mix(in srgb, var(--surface-raised) 88%, transparent);
    }

    .metric-label { display: block; color: var(--text-muted); font-size: 0.82rem; font-weight: 700; }
    .metric-value { display: block; margin-top: 8px; font-size: clamp(1.45rem, 4vw, 2rem); font-weight: 820; line-height: 1; }
    .metric-note { display: block; margin-top: 8px; color: var(--text-muted); font-size: 0.8rem; }

    .section-card { overflow: clip; }

    .section-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      padding: 22px 24px;
      border-bottom: 1px solid var(--border);
    }

    .section-header p { margin: 5px 0 0; color: var(--text-muted); max-width: 72ch; }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 14px 24px;
      border-bottom: 1px solid var(--border);
      background: var(--surface-muted);
    }

    .toolbar-status { margin: 0 0 0 auto; color: var(--text-muted); font-size: 0.88rem; }

    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: var(--control-height);
      min-width: 44px;
      padding: 9px 14px;
      border: 1px solid transparent;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 750;
      line-height: 1.2;
      text-decoration: none;
      transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
    }

    .button:hover:not(:disabled) { transform: translateY(-1px); }
    .button:active:not(:disabled) { transform: translateY(0); }
    .button:disabled { cursor: wait; opacity: 0.64; }

    .button-primary { color: #ffffff; background: #1957d2; border-color: #1957d2; }
    .button-primary:hover:not(:disabled) { background: #1248b5; border-color: #1248b5; }

    .button-secondary { color: var(--text); background: var(--surface); border-color: var(--border-strong); }
    .button-secondary:hover:not(:disabled) { background: var(--surface-muted); }

    .button-quiet { color: var(--accent); background: transparent; border-color: var(--border); }
    .button-quiet:hover:not(:disabled) { background: var(--accent-soft); }

    .button-small { min-height: var(--control-height); padding: 7px 11px; font-size: 0.86rem; }

    .control {
      min-height: var(--control-height);
      min-width: min(100%, 240px);
      padding: 9px 12px;
      border: 1px solid var(--border-strong);
      border-radius: 10px;
      color: var(--text);
      background: var(--surface);
    }

    .control::placeholder { color: var(--text-muted); opacity: 0.9; }

    .search-wrap { position: relative; flex: 1 1 260px; max-width: 420px; }
    .search-wrap .control { width: 100%; padding-left: 38px; }
    .search-icon { position: absolute; left: 13px; top: 50%; transform: translateY(-50%); color: var(--text-muted); pointer-events: none; }

    .table-wrap { width: 100%; overflow-x: auto; }

    table {
      width: 100%;
      border-collapse: collapse;
      border-spacing: 0;
    }

    caption {
      padding: 14px 24px 0;
      color: var(--text-muted);
      font-size: 0.88rem;
      text-align: left;
    }

    th, td {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }

    thead th {
      color: var(--text-muted);
      background: var(--surface-muted);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0.035em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    tbody tr:last-child > * { border-bottom: 0; }
    tbody tr:hover { background: color-mix(in srgb, var(--accent-soft) 34%, transparent); }

    .service-name { font-weight: 800; }
    .service-target { color: var(--text-muted); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.82rem; }
    .service-actions { display: flex; flex-wrap: wrap; gap: 8px; }

    .status-line {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 30px;
      color: var(--text-muted);
      font-size: 0.88rem;
      font-weight: 650;
    }

    .status-line::before {
      content: "";
      flex: 0 0 auto;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: currentColor;
    }

    .tone-success { color: var(--success); }
    .tone-danger { color: var(--danger); }
    .tone-warning { color: var(--warning); }
    .tone-neutral { color: var(--text-muted); }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 800;
      white-space: nowrap;
    }

    .badge-success { color: var(--success); background: var(--success-soft); }
    .badge-danger { color: var(--danger); background: var(--danger-soft); }
    .badge-warning { color: var(--warning); background: var(--warning-soft); }
    .badge-neutral { color: var(--text-muted); background: var(--surface-muted); }

    .certificate-layout {
      display: grid;
      grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
      gap: 18px;
    }

    .definition-grid {
      display: grid;
      grid-template-columns: minmax(130px, 0.7fr) minmax(0, 1.3fr);
      margin: 0;
    }

    .definition-grid dt,
    .definition-grid dd {
      margin: 0;
      padding: 11px 0;
      border-bottom: 1px solid var(--border);
    }

    .definition-grid dt { color: var(--text-muted); font-weight: 700; }
    .definition-grid dd { min-width: 0; font-weight: 650; overflow-wrap: anywhere; }
    .definition-grid > :nth-last-child(-n + 2) { border-bottom: 0; }

    details {
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      background: var(--surface-muted);
    }

    details summary {
      min-height: var(--control-height);
      padding: 11px 14px;
      cursor: pointer;
      font-weight: 750;
    }

    details[open] summary { border-bottom: 1px solid var(--border); }

    .details-body { padding: 14px; }

    pre {
      max-height: 420px;
      margin: 0;
      padding: 14px;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      background: var(--surface);
      font: 0.82rem/1.55 ui-monospace, SFMono-Regular, Consolas, monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .empty-state {
      padding: 30px 24px;
      color: var(--text-muted);
      text-align: center;
    }

    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid currentColor;
      border-right-color: transparent;
      border-radius: 50%;
      animation: spin 700ms linear infinite;
      vertical-align: -0.15em;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    .sr-only {
      position: absolute !important;
      width: 1px !important;
      height: 1px !important;
      padding: 0 !important;
      margin: -1px !important;
      overflow: hidden !important;
      clip: rect(0, 0, 0, 0) !important;
      white-space: nowrap !important;
      border: 0 !important;
    }

    .site-footer {
      padding: 0 0 32px;
      color: var(--text-muted);
      font-size: 0.86rem;
    }

    .site-footer .shell {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
    }

    @media (max-width: 900px) {
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .certificate-layout { grid-template-columns: 1fr; }
    }

    @media (max-width: 720px) {
      .shell { width: min(calc(100% - 20px), var(--content)); }
      .site-header { padding-top: 18px; }
      .topbar, .overview-heading, .section-header { align-items: stretch; flex-direction: column; }
      .header-actions { justify-content: flex-start; }
      .section-header, .toolbar { padding-inline: 16px; }
      .card-body { padding: 18px 16px; }
      .toolbar-status { width: 100%; margin-left: 0; }

      .responsive-table thead { display: none; }
      .responsive-table,
      .responsive-table tbody,
      .responsive-table tr,
      .responsive-table th,
      .responsive-table td { display: block; width: 100%; }
      .responsive-table tbody { padding: 10px; }
      .responsive-table tr {
        margin-bottom: 10px;
        overflow: hidden;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: var(--surface);
      }
      .responsive-table tr:last-child { margin-bottom: 0; }
      .responsive-table th,
      .responsive-table td {
        display: grid;
        grid-template-columns: minmax(92px, 0.42fr) minmax(0, 1fr);
        gap: 12px;
        padding: 11px 12px;
        border-bottom: 1px solid var(--border);
      }
      .responsive-table th::before,
      .responsive-table td::before {
        content: attr(data-label);
        color: var(--text-muted);
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        text-transform: uppercase;
      }
      .responsive-table tr > :last-child { border-bottom: 0; }
      .service-actions { align-items: flex-start; flex-direction: column; }
      .button-small { width: 100%; }
      .definition-grid { grid-template-columns: 1fr; }
      .definition-grid dt { padding-bottom: 2px; border-bottom: 0; }
      .definition-grid dd { padding-top: 2px; }
      .definition-grid > :nth-last-child(-n + 2) { border-bottom: 0; }
      .site-footer .shell { flex-direction: column; }
    }

    @media (max-width: 460px) {
      .metric-grid { grid-template-columns: 1fr; }
      .brand-mark { width: 42px; height: 42px; }
      .header-actions .button { flex: 1 1 auto; }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }
    }

    @media (prefers-contrast: more) {
      :root { --border: var(--border-strong); }
      .card, .metric, details { border-width: 2px; }
    }

    @media print {
      .skip-link, .section-nav, .header-actions, .toolbar, .service-actions { display: none !important; }
      body { background: #ffffff; color: #000000; }
      .card { box-shadow: none; break-inside: avoid; }
      .shell { width: 100%; max-width: none; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to dashboard content</a>

  <header class="site-header">
    <div class="shell">
      <div class="topbar">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">CR</div>
          <div>
            <p class="eyebrow">Reverse proxy operations</p>
            <h1 id="page-title">certify-reverse</h1>
            <p class="subtitle" id="page-subtitle">Loading runtime status…</p>
          </div>
        </div>
        <div class="header-actions" aria-label="Dashboard preferences">
          <button class="button button-secondary" id="theme-toggle" type="button">
            Theme: system
          </button>
        </div>
      </div>

      <nav class="section-nav" aria-label="Dashboard sections">
        <a href="#overview">Overview</a>
        <a href="#services">Services</a>
        <a href="#certificates">Certificates</a>
        <a href="#acme">ACME</a>
        <a href="#system">System</a>
      </nav>
    </div>
  </header>

  <main class="shell stack" id="main-content" tabindex="-1">
    <section id="overview" aria-labelledby="overview-title">
      <div class="card overview-card">
        <div class="overview-heading">
          <div>
            <p class="eyebrow">Current snapshot</p>
            <h2 id="overview-title">Operational overview</h2>
            <p id="overview-description">Service reachability and certificate checks update independently. HTTP error responses still count as reachable because the upstream answered.</p>
          </div>
          <p class="status-line tone-neutral" id="global-status" role="status" aria-atomic="true">Preparing checks…</p>
        </div>

        <div class="metric-grid" aria-label="Operational summary">
          <article class="metric">
            <span class="metric-label">Configured services</span>
            <strong class="metric-value" id="metric-services">0</strong>
            <span class="metric-note" id="metric-services-note">from upstream configuration</span>
          </article>
          <article class="metric">
            <span class="metric-label">Reachable</span>
            <strong class="metric-value" id="metric-reachable">0 / 0</strong>
            <span class="metric-note">latest HTTP probe</span>
          </article>
          <article class="metric">
            <span class="metric-label">TLS checks</span>
            <strong class="metric-value" id="metric-tls">0 / 0</strong>
            <span class="metric-note">best-effort HTTPS reachability</span>
          </article>
          <article class="metric">
            <span class="metric-label">Caddy release</span>
            <strong class="metric-value" id="metric-caddy">Unknown</strong>
            <span class="metric-note" id="metric-caddy-note">version comparison unavailable</span>
          </article>
        </div>
      </div>
    </section>

    <section id="services" aria-labelledby="services-title">
      <div class="card section-card">
        <header class="section-header">
          <div>
            <p class="eyebrow">Traffic paths</p>
            <h2 id="services-title">Services</h2>
            <p>Open public endpoints, inspect upstream targets, and rerun reachability checks without leaving the dashboard.</p>
          </div>
          <button class="button button-primary" id="check-all-services" type="button">Run all checks</button>
        </header>

        <div class="toolbar">
          <div class="search-wrap">
            <span class="search-icon" aria-hidden="true">⌕</span>
            <label class="sr-only" for="service-filter">Filter services</label>
            <input class="control" id="service-filter" type="search" inputmode="search" placeholder="Filter by service, URL, or target" autocomplete="off">
          </div>
          <p class="toolbar-status" id="service-filter-status" role="status" aria-atomic="true">Showing all services</p>
        </div>

        <div class="table-wrap">
          <table class="responsive-table" aria-describedby="services-note">
            <caption>Configured reverse-proxy services and their latest checks.</caption>
            <thead>
              <tr>
                <th scope="col">Service</th>
                <th scope="col">Public endpoint</th>
                <th scope="col">Upstream target</th>
                <th scope="col">Ping</th>
                <th scope="col">TLS</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody id="service-body"></tbody>
          </table>
        </div>
        <p class="empty-state" id="service-empty" hidden>No services match this filter.</p>
        <p class="sr-only" id="services-note">TLS checks confirm that an HTTPS response can be established through the status probe. Browsers cannot expose peer certificate details to this page.</p>
      </div>
    </section>

    <section id="certificates" class="certificate-layout" aria-label="Certificate information">
      <article class="card section-card" aria-labelledby="certificate-status-title">
        <header class="section-header">
          <div>
            <p class="eyebrow">Latest public record</p>
            <h2 id="certificate-status-title">Certificate status</h2>
            <p id="certificate-domain">Loading domain…</p>
          </div>
          <button class="button button-secondary" id="refresh-certificate-status" type="button">Refresh live</button>
        </header>
        <div class="card-body">
          <p class="status-line tone-neutral" id="certificate-loading" role="status" aria-atomic="true">Loading local crt.sh snapshot…</p>
          <dl class="definition-grid" id="certificate-summary">
            <dt>Common name</dt><dd id="cert-common-name">Not available</dd>
            <dt>Validity</dt><dd><span class="badge badge-neutral" id="cert-validity">Unknown</span></dd>
            <dt>Valid from</dt><dd id="cert-valid-from">Not available</dd>
            <dt>Valid until</dt><dd id="cert-valid-until">Not available</dd>
            <dt>Result count</dt><dd id="cert-result-count">0</dd>
            <dt>Last queried</dt><dd id="cert-last-queried">Not available</dd>
          </dl>
        </div>
      </article>

      <article class="card section-card" aria-labelledby="history-title">
        <header class="section-header">
          <div>
            <p class="eyebrow">Certificate transparency</p>
            <h2 id="history-title">crt.sh history</h2>
            <p>Search the normalized certificate history loaded from the local snapshot or live endpoint.</p>
          </div>
        </header>
        <div class="toolbar">
          <div class="search-wrap">
            <span class="search-icon" aria-hidden="true">⌕</span>
            <label class="sr-only" for="history-filter">Filter certificate history</label>
            <input class="control" id="history-filter" type="search" inputmode="search" placeholder="Filter certificate records" autocomplete="off">
          </div>
          <button class="button button-secondary" id="refresh-history-local" type="button">Local snapshot</button>
          <button class="button button-primary" id="refresh-history-live" type="button">Refresh live</button>
          <p class="toolbar-status" id="history-status" role="status" aria-atomic="true">No history loaded</p>
        </div>
        <div class="table-wrap">
          <table aria-describedby="history-status">
            <caption>Certificate transparency records. At most 200 filtered rows are rendered for browser performance.</caption>
            <thead>
              <tr>
                <th scope="col">Common name</th>
                <th scope="col">Issuer</th>
                <th scope="col">Valid from</th>
                <th scope="col">Valid until</th>
                <th scope="col">Logged</th>
                <th scope="col">ID</th>
              </tr>
            </thead>
            <tbody id="history-body"></tbody>
          </table>
        </div>
        <p class="empty-state" id="history-empty">Load a snapshot to view certificate records.</p>
      </article>
    </section>

    <section id="acme" aria-labelledby="acme-title">
      <article class="card section-card">
        <header class="section-header">
          <div>
            <p class="eyebrow">Automation state</p>
            <h2 id="acme-title">ACME state</h2>
            <p>Runtime challenge details are summarized first; raw JSON remains available for diagnosis.</p>
          </div>
          <button class="button button-secondary" id="refresh-acme" type="button">Refresh state</button>
        </header>
        <div class="card-body stack">
          <p class="status-line tone-neutral" id="acme-status" role="status" aria-atomic="true">Loading ACME state…</p>
          <dl class="definition-grid">
            <dt>State</dt><dd id="acme-state-value">Unknown</dd>
            <dt>Subjects</dt><dd id="acme-subjects">None reported</dd>
            <dt>Generated</dt><dd id="acme-generated">Not available</dd>
            <dt>Note</dt><dd id="acme-note">No note reported</dd>
          </dl>
          <details>
            <summary>Raw ACME state JSON</summary>
            <div class="details-body"><pre id="acme-json">Loading…</pre></div>
          </details>
        </div>
      </article>
    </section>

    <section id="system" aria-labelledby="system-title">
      <article class="card section-card">
        <header class="section-header">
          <div>
            <p class="eyebrow">Build provenance</p>
            <h2 id="system-title">System information</h2>
            <p>Version and generation metadata for the currently rendered dashboard.</p>
          </div>
        </header>
        <div class="card-body">
          <dl class="definition-grid" id="system-meta">
            <dt>Domain</dt><dd id="meta-domain">Unknown</dd>
            <dt>Operator email</dt><dd id="meta-email">Unknown</dd>
            <dt>DNS provider</dt><dd id="meta-provider">Unknown</dd>
            <dt>Caddy requested</dt><dd id="meta-caddy-requested">Unknown</dd>
            <dt>Caddy built</dt><dd id="meta-caddy-built">Unknown</dd>
            <dt>Caddy latest</dt><dd id="meta-caddy-latest">Unknown</dd>
            <dt>Native upgrade</dt><dd id="meta-native-upgrade">Unknown</dd>
            <dt>Application version</dt><dd id="meta-app-version">Unknown</dd>
            <dt>Application commit</dt><dd id="meta-app-commit">Unknown</dd>
            <dt>Generated</dt><dd id="meta-generated">Unknown</dd>
          </dl>
        </div>
      </article>
    </section>
  </main>

  <footer class="site-footer">
    <div class="shell">
      <span id="footer-version">certify-reverse</span>
      <span id="footer-generated">Operational dashboard</span>
    </div>
  </footer>

  <div class="sr-only" id="announcer" role="status" aria-live="polite" aria-atomic="true"></div>

  <script>
    const services = __CERTIFY_SERVICES_JSON__;
    const meta = __CERTIFY_META_JSON__;
    const serviceState = new Map();
    let historyRows = [];

    const byId = (id) => document.getElementById(id);
    const text = (id, value) => { byId(id).textContent = value == null || value === '' ? 'Not available' : String(value); };

    function announce(message) {
      const el = byId('announcer');
      el.textContent = '';
      window.setTimeout(() => { el.textContent = message; }, 20);
    }

    function formatDate(value) {
      if (!value) return 'Not available';
      const raw = String(value);
      const normalized = raw.includes('T') ? raw : raw.includes(' ') ? raw.replace(' ', 'T') + 'Z' : raw + 'T00:00:00Z';
      const date = new Date(normalized);
      if (Number.isNaN(date.getTime())) return raw;
      return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: raw.length > 10 ? 'short' : undefined,
      }).format(date);
    }

    function setStatus(element, message, tone = 'neutral') {
      element.textContent = message;
      element.className = `status-line tone-${tone}`;
    }

    function setBusy(button, busy, busyLabel = 'Working…') {
      if (!button.dataset.label) button.dataset.label = button.textContent;
      button.disabled = busy;
      button.setAttribute('aria-busy', String(busy));
      button.textContent = busy ? busyLabel : button.dataset.label;
    }

    async function fetchJson(url, timeoutMs = 15000) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
      } finally {
        window.clearTimeout(timer);
      }
    }

    function initialiseTheme() {
      const allowed = new Set(['system', 'light', 'dark']);
      let saved = 'system';
      try { saved = localStorage.getItem('certify-reverse-theme') || 'system'; } catch (_) { /* storage may be blocked */ }
      applyTheme(allowed.has(saved) ? saved : 'system');
      byId('theme-toggle').addEventListener('click', () => {
        const current = document.documentElement.dataset.theme || 'system';
        const next = current === 'system' ? 'light' : current === 'light' ? 'dark' : 'system';
        applyTheme(next);
        announce(`Theme changed to ${next}`);
      });
    }

    function applyTheme(theme) {
      document.documentElement.dataset.theme = theme;
      const button = byId('theme-toggle');
      button.textContent = `Theme: ${theme}`;
      button.setAttribute('aria-label', `Color theme: ${theme}. Activate to change theme.`);
      try { localStorage.setItem('certify-reverse-theme', theme); } catch (_) { /* storage may be blocked */ }
    }

    function initialiseMeta() {
      const version = meta.certify_reverse_version || 'unknown';
      document.title = `certify-reverse v${version} status`;
      text('page-title', `certify-reverse v${version}`);
      text('page-subtitle', meta.domain ? `Operational status for ${meta.domain}` : 'Operational status');
      text('meta-domain', meta.domain);
      text('meta-email', meta.email);
      text('meta-provider', meta.dns_provider);
      text('meta-caddy-requested', meta.caddy_requested_version);
      text('meta-caddy-built', meta.caddy_built_version);
      text('meta-caddy-latest', meta.caddy_latest_version);
      text(
        'meta-native-upgrade',
        meta.caddy_native_upgrade_supported === true
          ? 'Available'
          : meta.caddy_native_upgrade_supported === false
            ? 'Not available'
            : 'Unknown',
      );
      text('meta-app-version', version);
      text('meta-app-commit', meta.certify_reverse_commit);
      text('meta-generated', formatDate(meta.generated_at));
      text('footer-version', `certify-reverse v${version}`);
      text('footer-generated', `Generated ${formatDate(meta.generated_at)}`);
      text('certificate-domain', meta.domain || 'Unknown domain');

      text('metric-services', services.length);
      text('metric-services-note', services.length === 1 ? 'configured upstream' : 'configured upstreams');
      if (meta.caddy_update_recommended === true) {
        text('metric-caddy', 'Update');
        text('metric-caddy-note', `${meta.caddy_built_version || 'unknown'} → ${meta.caddy_latest_version || 'unknown'}`);
      } else if (meta.caddy_update_recommended === false) {
        text('metric-caddy', 'Current');
        text('metric-caddy-note', meta.caddy_built_version || 'installed version');
      } else {
        text('metric-caddy', 'Unknown');
        text('metric-caddy-note', 'version comparison unavailable');
      }
    }

    function createCell(label, content, tagName = 'td') {
      const cell = document.createElement(tagName);
      cell.dataset.label = label;
      if (typeof content === 'string') cell.textContent = content;
      else if (content) cell.append(content);
      return cell;
    }

    function serviceStatusElement(kind, serviceName) {
      const el = document.createElement('span');
      el.id = `${kind}-status-${serviceName}`;
      el.className = 'status-line tone-neutral';
      el.setAttribute('aria-label', `${kind} status for ${serviceName}`);
      el.textContent = 'Not checked';
      return el;
    }

    function serviceAction(label, handler) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button button-quiet button-small';
      button.textContent = label;
      button.addEventListener('click', handler);
      return button;
    }

    function createServiceRow(service) {
      const row = document.createElement('tr');
      row.dataset.search = `${service.name} ${service.url} ${service.target}`.toLowerCase();

      const name = document.createElement('span');
      name.className = 'service-name';
      name.textContent = service.name;
      row.append(createCell('Service', name, 'th'));
      row.lastElementChild.scope = 'row';

      const link = document.createElement('a');
      link.href = service.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = service.url;
      link.setAttribute('aria-label', `${service.name} public endpoint, opens in a new tab`);
      row.append(createCell('Public endpoint', link));

      const target = document.createElement('code');
      target.className = 'service-target';
      target.textContent = service.target;
      row.append(createCell('Upstream target', target));

      row.append(createCell('Ping', serviceStatusElement('ping', service.name)));
      row.append(createCell('TLS', serviceStatusElement('tls', service.name)));

      const actions = document.createElement('div');
      actions.className = 'service-actions';
      const pingButton = serviceAction('Check ping', () => runServiceCheck(service, 'ping', pingButton));
      const tlsButton = serviceAction('Check TLS', () => runServiceCheck(service, 'tls', tlsButton));
      actions.append(pingButton, tlsButton);
      row.append(createCell('Actions', actions));

      return row;
    }

    function renderServices() {
      const body = byId('service-body');
      body.replaceChildren();
      services.forEach((service) => {
        serviceState.set(service.name, { ping: 'idle', tls: 'idle' });
        body.append(createServiceRow(service));
      });
      filterServices();
      updateMetrics();
    }

    function filterServices() {
      const query = byId('service-filter').value.trim().toLowerCase();
      const rows = Array.from(byId('service-body').rows);
      let visible = 0;
      rows.forEach((row) => {
        const show = !query || row.dataset.search.includes(query);
        row.hidden = !show;
        if (show) visible += 1;
      });
      byId('service-empty').hidden = visible !== 0;
      byId('service-empty').textContent = services.length === 0
        ? 'No upstream services are configured.'
        : 'No services match this filter.';
      byId('service-filter-status').textContent = query
        ? `Showing ${visible} of ${services.length} services`
        : `Showing all ${services.length} services`;
    }

    async function probe(url, method) {
      const started = performance.now();
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 12000);
      try {
        let response = await fetch(url, { method, mode: 'cors', cache: 'no-store', signal: controller.signal });
        if (method === 'HEAD' && response.status === 405) {
          response = await fetch(url, { method: 'GET', mode: 'cors', cache: 'no-store', signal: controller.signal });
        }
        const elapsed = Math.round(performance.now() - started);
        return { ok: true, message: `HTTP ${response.status} · ${elapsed} ms` };
      } catch (error) {
        const message = error && error.name === 'AbortError' ? 'Timed out after 12 s' : `Unreachable · ${error.message}`;
        return { ok: false, message };
      } finally {
        window.clearTimeout(timer);
      }
    }

    async function runServiceCheck(service, kind, button = null) {
      const status = byId(`${kind}-status-${service.name}`);
      if (button) setBusy(button, true, 'Checking…');
      setStatus(status, 'Checking…', 'neutral');
      serviceState.get(service.name)[kind] = 'loading';
      updateMetrics();

      const result = await probe(service.probe_url, kind === 'ping' ? 'HEAD' : 'GET');
      serviceState.get(service.name)[kind] = result.ok ? 'ok' : 'error';
      setStatus(status, result.message, result.ok ? 'success' : 'danger');
      if (button) setBusy(button, false);
      updateMetrics();
      if (button) announce(`${service.name} ${kind}: ${result.message}`);
      return result;
    }

    async function runAllChecks(options = {}) {
      const button = byId('check-all-services');
      setBusy(button, true, 'Checking services…');
      setStatus(byId('global-status'), `Running ${services.length * 2} checks…`, 'neutral');
      const tasks = [];
      services.forEach((service) => {
        tasks.push(runServiceCheck(service, 'ping'));
        tasks.push(runServiceCheck(service, 'tls'));
      });
      await Promise.all(tasks);
      setBusy(button, false);
      const failed = Array.from(serviceState.values()).reduce(
        (total, state) => total + (state.ping === 'error' ? 1 : 0) + (state.tls === 'error' ? 1 : 0),
        0,
      );
      const message = failed === 0 ? 'All service checks completed successfully.' : `${failed} service checks need attention.`;
      setStatus(byId('global-status'), message, failed === 0 ? 'success' : 'warning');
      if (options.announce !== false) announce(message);
    }

    function updateMetrics() {
      let pingOk = 0;
      let pingDone = 0;
      let tlsOk = 0;
      let tlsDone = 0;
      serviceState.forEach((state) => {
        if (state.ping === 'ok') pingOk += 1;
        if (state.ping === 'ok' || state.ping === 'error') pingDone += 1;
        if (state.tls === 'ok') tlsOk += 1;
        if (state.tls === 'ok' || state.tls === 'error') tlsDone += 1;
      });
      text('metric-reachable', `${pingOk} / ${services.length}`);
      text('metric-tls', `${tlsOk} / ${services.length}`);
      byId('metric-reachable').setAttribute('aria-label', `${pingOk} of ${services.length} services reachable; ${pingDone} checked`);
      byId('metric-tls').setAttribute('aria-label', `${tlsOk} of ${services.length} TLS checks successful; ${tlsDone} checked`);
    }

    function parseDate(value) {
      if (!value) return null;
      const raw = String(value);
      const normalized = raw.includes('T') ? raw : raw.includes(' ') ? raw.replace(' ', 'T') + 'Z' : raw + 'T00:00:00Z';
      const date = new Date(normalized);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    function latestCertificate(rows) {
      let latest = null;
      rows.forEach((row) => {
        if (!latest) { latest = row; return; }
        const candidate = parseDate(row.not_after) || parseDate(row.entry_timestamp);
        const current = parseDate(latest.not_after) || parseDate(latest.entry_timestamp);
        if (candidate && (!current || candidate > current)) latest = row;
      });
      return latest;
    }

    function certificateValidity(row) {
      if (!row) return 'unknown';
      const now = new Date();
      const from = parseDate(row.not_before);
      const until = parseDate(row.not_after);
      if (from && until) return from <= now && now <= until ? 'valid' : 'expired/not-yet-valid';
      if (until) return now <= until ? 'valid' : 'expired';
      return 'unknown';
    }

    function renderCertificateSummary(snapshot) {
      const latest = snapshot && snapshot.latest ? snapshot.latest : null;
      const validity = snapshot && snapshot.latest_validity ? snapshot.latest_validity : certificateValidity(latest);
      text('certificate-domain', snapshot && snapshot.domain ? snapshot.domain : meta.domain);
      text('cert-common-name', latest && (latest.common_name || latest.name_value));
      text('cert-valid-from', latest ? formatDate(latest.not_before) : null);
      text('cert-valid-until', latest ? formatDate(latest.not_after) : null);
      text('cert-result-count', snapshot && snapshot.match_count != null ? snapshot.match_count : 0);
      text('cert-last-queried', formatDate(snapshot && (snapshot.last_queried || snapshot.generated_at)));

      const badge = byId('cert-validity');
      badge.textContent = validity || 'unknown';
      const tone = validity === 'valid' ? 'success' : validity && validity.includes('expired') ? 'danger' : validity === 'error' ? 'danger' : 'neutral';
      badge.className = `badge badge-${tone}`;
    }

    function normalizeHistoryRows(rows) {
      return (Array.isArray(rows) ? rows : []).map((row) => ({
        commonName: row && (row.common_name || row.name_value) ? String(row.common_name || row.name_value).replace(/\\n/g, ' · ') : '',
        issuer: row && row.issuer_name ? String(row.issuer_name) : '',
        validFrom: row && row.not_before ? String(row.not_before) : '',
        validUntil: row && row.not_after ? String(row.not_after) : '',
        logged: row && row.entry_timestamp ? String(row.entry_timestamp) : '',
        id: row && row.id != null ? String(row.id) : '',
      }));
    }

    function renderHistory() {
      const query = byId('history-filter').value.trim().toLowerCase();
      const filtered = historyRows.filter((row) =>
        !query || [row.commonName, row.issuer, row.validFrom, row.validUntil, row.logged, row.id]
          .some((value) => value.toLowerCase().includes(query)),
      );
      const visibleRows = filtered.slice(0, 200);
      const body = byId('history-body');
      body.replaceChildren();

      visibleRows.forEach((row) => {
        const tr = document.createElement('tr');
        [
          row.commonName || 'Not available',
          row.issuer || 'Not available',
          formatDate(row.validFrom),
          formatDate(row.validUntil),
          formatDate(row.logged),
          row.id || 'Not available',
        ].forEach((value) => {
          const td = document.createElement('td');
          td.textContent = value;
          tr.append(td);
        });
        body.append(tr);
      });

      byId('history-empty').hidden = visibleRows.length !== 0;
      byId('history-empty').textContent = historyRows.length === 0
        ? 'No certificate records are available.'
        : 'No certificate records match this filter.';
      const suffix = filtered.length > 200 ? ' · first 200 rendered' : '';
      byId('history-status').textContent = query
        ? `${filtered.length} of ${historyRows.length} records match${suffix}`
        : `${historyRows.length} records${suffix}`;
    }

    async function loadCertificateSnapshot() {
      setStatus(byId('certificate-loading'), 'Loading local crt.sh snapshot…', 'neutral');
      try {
        const snapshot = await fetchJson('/crtsh-state.json');
        if (snapshot.error) throw new Error(snapshot.error);
        const rows = Array.isArray(snapshot.entries) ? snapshot.entries : [];
        historyRows = normalizeHistoryRows(rows);
        renderCertificateSummary({ ...snapshot, last_queried: new Date().toISOString() });
        renderHistory();
        setStatus(byId('certificate-loading'), 'Local certificate snapshot loaded.', 'success');
      } catch (error) {
        renderCertificateSummary({ domain: meta.domain, latest_validity: 'error', match_count: 0 });
        historyRows = [];
        renderHistory();
        setStatus(byId('certificate-loading'), `Snapshot unavailable · ${error.message}`, 'danger');
      }
    }

    async function loadCertificateLive(triggerButton = null) {
      const buttons = [byId('refresh-certificate-status'), byId('refresh-history-live')];
      buttons.forEach((button) => setBusy(button, true, 'Refreshing…'));
      setStatus(byId('certificate-loading'), 'Querying live crt.sh data…', 'neutral');
      try {
        const rows = await fetchJson(`/probe/crtsh?q=${encodeURIComponent(meta.domain)}&output=json`, 20000);
        if (!Array.isArray(rows)) throw new Error('Unexpected response format');
        const latest = latestCertificate(rows);
        historyRows = normalizeHistoryRows(rows);
        renderCertificateSummary({
          domain: meta.domain,
          latest,
          latest_validity: certificateValidity(latest),
          match_count: rows.length,
          last_queried: new Date().toISOString(),
        });
        renderHistory();
        setStatus(byId('certificate-loading'), 'Live certificate data refreshed.', 'success');
        announce(`Live certificate data refreshed with ${rows.length} records.`);
      } catch (error) {
        setStatus(byId('certificate-loading'), `Live query failed · ${error.message}`, 'danger');
        announce(`Live certificate query failed: ${error.message}`);
      } finally {
        buttons.forEach((button) => setBusy(button, false));
      }
    }

    async function loadAcmeState() {
      const button = byId('refresh-acme');
      setBusy(button, true, 'Refreshing…');
      setStatus(byId('acme-status'), 'Loading ACME state…', 'neutral');
      try {
        const state = await fetchJson('/acme-state.json');
        text('acme-state-value', state.state || 'unknown');
        text('acme-subjects', Array.isArray(state.subjects) && state.subjects.length ? state.subjects.join(', ') : 'None reported');
        text('acme-generated', formatDate(state.generated_at));
        text('acme-note', state.note || 'No note reported');
        byId('acme-json').textContent = JSON.stringify(state, null, 2);
        setStatus(byId('acme-status'), 'ACME state loaded.', 'success');
      } catch (error) {
        text('acme-state-value', 'unavailable');
        byId('acme-json').textContent = `ACME state unavailable: ${error.message}`;
        setStatus(byId('acme-status'), `ACME state unavailable · ${error.message}`, 'danger');
      } finally {
        setBusy(button, false);
      }
    }

    function bindActions() {
      byId('service-filter').addEventListener('input', filterServices);
      byId('history-filter').addEventListener('input', renderHistory);
      byId('check-all-services').addEventListener('click', () => runAllChecks());
      byId('refresh-certificate-status').addEventListener('click', () => loadCertificateLive(byId('refresh-certificate-status')));
      byId('refresh-history-live').addEventListener('click', () => loadCertificateLive(byId('refresh-history-live')));
      byId('refresh-history-local').addEventListener('click', async () => {
        const button = byId('refresh-history-local');
        setBusy(button, true, 'Loading…');
        await loadCertificateSnapshot();
        setBusy(button, false);
      });
      byId('refresh-acme').addEventListener('click', loadAcmeState);
    }

    async function init() {
      initialiseTheme();
      initialiseMeta();
      renderServices();
      bindActions();
      await Promise.all([loadCertificateSnapshot(), loadAcmeState()]);
      if (services.length === 0) {
        setStatus(byId('global-status'), 'No upstream services are configured.', 'warning');
      } else {
        runAllChecks({ announce: false });
      }
    }

    init();
  </script>
</body>
</html>
"""
    return page.replace("__CERTIFY_SERVICES_JSON__", services_json).replace(
        "__CERTIFY_META_JSON__", meta_json
    )
