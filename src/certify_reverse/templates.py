#!/usr/bin/env python3
"""
Template rendering functions for Caddy and dnsmasq configurations.

This module contains all templating logic separated from the main application logic.
"""
import textwrap
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cli import ReverseProxyConfig, Upstream

# Global reference to data directory - will be set by main app
DATADIR = Path("/data")


def set_datadir(datadir: Path):
    """Set the data directory path for template rendering."""
    global DATADIR
    DATADIR = datadir


def render_caddy(cfg: 'ReverseProxyConfig') -> str:
    """Render Caddyfile configuration from ReverseProxyConfig."""
    # Global configuration block
    global_config = textwrap.dedent(
        f"""
    {{
        email {cfg.email}
        acme_dns {cfg.dns_provider} {{
            token {cfg.dns_token}
        }}
    }}
    """
    ).strip()

    blocks = []

    # Dedicated status host with server-side probes for more reliable browser checks.
    status_lines = [
        f"status.{cfg.domain} " + "{",
        "    header /probe/* Access-Control-Allow-Origin *",
        "    header /acme-state.json Access-Control-Allow-Origin *",
        "    header /crtsh-state.json Access-Control-Allow-Origin *",
        "    handle_path /probe/crtsh {",
        "        reverse_proxy https://crt.sh",
        "    }",
    ]
    for upstream in cfg.upstreams:
        status_lines.append(f"    handle_path /probe/{upstream.subdomain}/* " + "{")
        status_lines.append(
            f"        reverse_proxy {upstream.scheme}://{upstream.ip}:{upstream.port} " + "{"
        )
        if upstream.forward_auth_headers:
            status_lines.append("            header_up X-Real-IP {remote}")
        if upstream.is_https:
            transport_config = _render_transport_config(upstream)
            if transport_config:
                status_lines.append(f"            {transport_config}")
        status_lines.append("        }")
        status_lines.append("    }")
    status_lines.extend(
        [
            "    root * /data/",
            "    file_server",
            "}",
        ]
    )
    blocks.append("\n".join(status_lines))
    
    # Internal certificate server for services to get their certs
    blocks.append(
        textwrap.dedent(
            f"""
    # Internal certificate distribution endpoint
    internal-ca.{cfg.domain} {{
        handle /cert/* {{
            reverse_proxy localhost:2021
        }}
        handle {{
            respond "Caddy Internal CA Service" 200
        }}
    }}
    """
        )
    )
    
    # Wildcard convenience host
    blocks.append(
        textwrap.dedent(
            f"""
    *.{cfg.domain} {{
        root * /data/
        file_server
    }}
    """
        )
    )
    
    # Specific upstream configurations
    for upstream in cfg.upstreams:
        block = _render_upstream_block(upstream, cfg.domain)
        blocks.append(block)

    return "\n\n".join([global_config] + blocks)


def _render_upstream_block(upstream: 'Upstream', domain: str) -> str:
    """Render a single upstream configuration block."""
    rp_target = f"{upstream.scheme}://{upstream.ip}:{upstream.port}"
    block = [f"{upstream.subdomain}.{domain} " + "{"]
    block.append(f"    reverse_proxy {rp_target} " + "{")
    
    # Forward authentication headers if enabled
    if upstream.forward_auth_headers:
        block.append("        header_up X-Real-IP {remote}")
    
    # Handle HTTPS transport configuration
    if upstream.is_https:
        transport_config = _render_transport_config(upstream)
        if transport_config:
            block.append(f"        {transport_config}")
    
    block.append("    }")  # close reverse_proxy block
    block.append("}")      # close site block
    
    return "\n".join(block)


def _render_transport_config(upstream: 'Upstream') -> str:
    """Render transport configuration for HTTPS upstreams."""
    if upstream.skip_verify:
        return "transport http { tls_insecure_skip_verify }"
    elif upstream.trust_pool:
        pool_file = Path(upstream.trust_pool).expanduser()
        return f"transport http {{ tls_trust_pool file {pool_file} }}"
    else:
        # Use exported Caddy CA for verification
        ca_cert_path = DATADIR / "exported-certs" / "caddy-internal-ca.pem"
        return f"transport http {{ tls_trust_pool file {ca_cert_path} }}"


def render_dnsmasq(cfg: 'ReverseProxyConfig') -> str:
    """Render dnsmasq configuration from ReverseProxyConfig."""
    # Wildcard domain -> reverse-proxy host IP
    target_ip = getattr(cfg, "dnsmasq_address_ip", "10.0.0.1")
    return textwrap.dedent(
        f"""
    no-resolv
    log-queries
    log-facility=/data/logs/dnsmasq.log
    address=/.{cfg.domain}/{target_ip}
    """
    ).lstrip()


def render_upstream_tls_setup_guide(cert_info: dict) -> str:
    """Render the upstream TLS setup guide markdown content."""
    import time
    
    return f"""# Upstream TLS Configuration

## Caddy Internal Certificate Export

Caddy's internal root CA has been exported to:
- **PEM format**: `{cert_info['ca_cert_pem']}`
- **CRT format**: `{cert_info['ca_cert_crt']}`

## ⚠️ Certificate Expiration Notice

**Important**: This CA certificate expires in **25 years** from creation.
- **Root CA**: 25 year lifetime
- **Intermediate CA**: 5 year lifetime (auto-renewed by Caddy)
- **Monitor expiration**: Use `caddy pki ca list` to check status
- **Renewal**: When root CA expires, export new certificates and update all services

## Configure Your Upstream Services

### For Docker Services:
```yaml
# In your docker-compose.yml for upstream services
volumes:
  - {cert_info['export_dir']}:/etc/ssl/caddy:ro

# Then in your application:
# Use /etc/ssl/caddy/caddy-internal-ca.pem as trusted CA
```

### For Node.js Applications:
```javascript
// Set the CA certificate
process.env.NODE_EXTRA_CA_CERTS = '/etc/ssl/caddy/caddy-internal-ca.pem';

// Or in HTTPS requests:
const https = require('https');
const fs = require('fs');

const ca = fs.readFileSync('/etc/ssl/caddy/caddy-internal-ca.pem');
const options = {{
  ca: ca,
  // ... other options
}};
```

### For Python Applications:
```python
import ssl
import requests

# Create SSL context with Caddy CA
context = ssl.create_default_context(cafile='/etc/ssl/caddy/caddy-internal-ca.pem')

# Use with requests
session = requests.Session()
session.verify = '/etc/ssl/caddy/caddy-internal-ca.pem'
```

### For Go Applications:
```go
package main

import (
    "crypto/tls"
    "crypto/x509"
    "io/ioutil"
)

func setupTLS() *tls.Config {{
    caCert, _ := ioutil.ReadFile("/etc/ssl/caddy/caddy-internal-ca.pem")
    caCertPool := x509.NewCertPool()
    caCertPool.AppendCertsFromPEM(caCert)
    
    return &tls.Config{{
        RootCAs: caCertPool,
    }}
}}
```

### For Debian/Ubuntu System-Wide Installation:
```bash
# Install CA certificate system-wide on Debian/Ubuntu
sudo cp {cert_info['ca_cert_crt']} /usr/local/share/ca-certificates/
sudo update-ca-certificates

# Verify installation
sudo update-ca-certificates --verbose | grep caddy-internal-ca

# Test system-wide trust
echo | openssl s_client -connect your-service:8443 -verify_return_error
```

**Docker containers on Debian-based images:**
```dockerfile
# In Dockerfile
COPY {cert_info['ca_cert_crt']} /usr/local/share/ca-certificates/
RUN update-ca-certificates

# Or mount in docker-compose.yml and run update-ca-certificates
```

## Environment Variables for Services:
```bash
# Common environment variables to set:
SSL_CERT_FILE=/etc/ssl/caddy/caddy-internal-ca.pem
CADDY_CA_CERT=/etc/ssl/caddy/caddy-internal-ca.pem
REQUESTS_CA_BUNDLE=/etc/ssl/caddy/caddy-internal-ca.pem
```

Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""


def render_status_index_html(cfg: "ReverseProxyConfig", public_meta: dict) -> str:
    """Render a simple dashboard with service ping/check actions."""
    services = [
        {
            "name": u.subdomain,
            "url": f"https://{u.subdomain}.{cfg.domain}",
            "probe_url": f"https://status.{cfg.domain}/probe/{u.subdomain}/",
            "target": f"{u.scheme}://{u.ip}:{u.port}",
            "scheme": u.scheme,
        }
        for u in cfg.upstreams
    ]

    services_json = json.dumps(services)
    meta_json = json.dumps(public_meta)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>certify-reverse status</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --card: #ffffff;
      --ink: #1f2937;
      --muted: #6b7280;
      --ok: #0a7f37;
      --bad: #b00020;
      --accent: #0b5fff;
      --line: #dbe2ea;
    }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background: linear-gradient(160deg, #eef3ff 0%, var(--bg) 45%, #fefefe 100%);
    }}
    .wrap {{ max-width: 1024px; margin: 24px auto; padding: 0 16px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(10, 20, 40, 0.05);
      margin-bottom: 16px;
    }}
    h1, h2 {{ margin: 0 0 10px 0; }}
    .meta p {{ margin: 4px 0; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); font-size: 14px; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .btn {{
      background: var(--accent);
      color: #fff;
      border: 0;
      border-radius: 8px;
      padding: 6px 10px;
      cursor: pointer;
      font-size: 12px;
    }}
    .status-ok {{ color: var(--ok); font-weight: 600; }}
    .status-bad {{ color: var(--bad); font-weight: 600; }}
    .status-unknown {{ color: var(--muted); font-weight: 600; }}
    .note {{ color: var(--muted); font-size: 12px; }}
    .scroll-x {{ overflow-x: auto; }}
    .toolbar {{ display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
    .kv p {{ margin: 4px 0; }}
    .cell-action {{ display: inline-flex; gap: 6px; align-items: center; }}
    .btn-inline {{
      background: transparent;
      color: var(--accent);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 1px 6px;
      cursor: pointer;
      font-size: 12px;
      line-height: 1.2;
    }}
    .spinner {{
      width: 18px;
      height: 18px;
      border: 2px solid var(--line);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: inline-block;
      vertical-align: middle;
      margin-right: 8px;
    }}
    @keyframes spin {{
      from {{ transform: rotate(0deg); }}
      to {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1 id="title">certify-reverse Dashboard</h1>
      <div class="meta" id="meta"></div>
    </div>
    <div class="card">
      <h2>crt.sh Status <span id="crtsh-domain"></span></h2>
      <p class="note" id="crtsh-loading"><span class="spinner"></span>Querying crt.sh status...</p>
      <div class="toolbar">
        <button class="btn" id="crtsh-refresh-status">↻ Refresh</button>
      </div>
      <div class="kv" id="crtsh-status"></div>
    </div>
    <div class="card">
      <h2>Services</h2>
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Public URL</th>
            <th>Upstream Target</th>
            <th>Ping</th>
            <th>Cert</th>
          </tr>
        </thead>
        <tbody id="svc-body"></tbody>
      </table>
      <p class="note">Browser clients cannot read TLS certificate details directly; certificate check is a best-effort HTTPS reachability probe.</p>
    </div>
    <div class="card">
      <h2>ACME State</h2>
      <pre id="acme-state">loading...</pre>
    </div>
    <div class="card">
      <h2>crt.sh Certificate History</h2>
      <p class="note" id="crtsh-summary">loading...</p>
      <div class="toolbar">
        <button class="btn" id="crtsh-refresh-local">Refresh Local Snapshot</button>
        <button class="btn" id="crtsh-refresh-live">Refresh Live (via /probe/crtsh)</button>
      </div>
      <div class="scroll-x">
        <table>
          <thead id="crtsh-head"></thead>
          <tbody id="crtsh-body"></tbody>
        </table>
      </div>
    </div>
  </div>
  <script>
    const services = {services_json};
    const meta = {meta_json};

    function esc(s) {{
      return String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
    }}

    function setMeta() {{
      const t = document.getElementById('title');
      const appVer = meta.certify_reverse_version || 'unknown';
      t.textContent = `certify-reverse v${{appVer}} Dashboard`;
      const el = document.getElementById('meta');
      el.innerHTML = `
        <p><strong>certify-reverse version:</strong> ${{esc(meta.certify_reverse_version || 'unknown')}}</p>
        <p><strong>certify-reverse commit:</strong> ${{esc(meta.certify_reverse_commit || 'unknown')}}</p>
        <p><strong>Domain:</strong> ${{esc(meta.domain)}}</p>
        <p><strong>Email:</strong> ${{esc(meta.email)}}</p>
        <p><strong>DNS Provider:</strong> ${{esc(meta.dns_provider)}}</p>
        <p><strong>Caddy Requested:</strong> ${{esc(meta.caddy_requested_version)}}</p>
        <p><strong>Caddy Built:</strong> ${{esc(meta.caddy_built_version)}}</p>
        <p><strong>Caddy Latest:</strong> ${{esc(meta.caddy_latest_version)}} (${{meta.caddy_update_recommended ? 'update recommended' : 'up-to-date/unknown'}})</p>
        <p><strong>Native Upgrade Cmd:</strong> ${{meta.caddy_native_upgrade_supported ? 'available' : 'not available'}}</p>
        <p><strong>Generated At:</strong> ${{esc(meta.generated_at)}}</p>
      `;
    }}

    async function ping(probeUrl) {{
      const started = performance.now();
      try {{
        const r = await fetch(probeUrl, {{ method: 'HEAD', mode: 'cors', cache: 'no-store' }});
        const ms = Math.round(performance.now() - started);
        return `HTTP ${{r.status}} (~${{ms}}ms)`;
      }} catch (e) {{
        return `unreachable (${{e.message}})`;
      }}
    }}

    async function certCheck(probeUrl) {{
      try {{
        const r = await fetch(probeUrl, {{ method: 'GET', mode: 'cors', cache: 'no-store' }});
        return `probe TLS/HTTP reachable (status ${{r.status}})`;
      }} catch (e) {{
        return `https check failed: ${{e.message}}`;
      }}
    }}

    function rowForService(svc) {{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${{esc(svc.name)}}</td>
        <td><a href="${{esc(svc.url)}}" target="_blank" rel="noreferrer">${{esc(svc.url)}}</a></td>
        <td>${{esc(svc.target)}}</td>
        <td><span class="cell-action"><span id="ping-res-${{esc(svc.name)}}" class="note">checking...</span><button class="btn-inline" id="ping-refresh-${{esc(svc.name)}}" title="Refresh ping">↻</button></span></td>
        <td><span class="cell-action"><span id="cert-res-${{esc(svc.name)}}" class="note">checking...</span><button class="btn-inline" id="cert-refresh-${{esc(svc.name)}}" title="Refresh cert check">↻</button></span></td>
      `;
      return tr;
    }}

    async function loadAcmeState() {{
      const el = document.getElementById('acme-state');
      try {{
        const r = await fetch('/acme-state.json', {{ cache: 'no-store' }});
        const j = await r.json();
        el.textContent = JSON.stringify(j, null, 2);
      }} catch (e) {{
        el.textContent = `acme-state unavailable: ${{e.message}}`;
      }}
    }}

    function renderCrtShEntries(entries, summaryText) {{
      const summary = document.getElementById('crtsh-summary');
      const head = document.getElementById('crtsh-head');
      const body = document.getElementById('crtsh-body');
      summary.textContent = summaryText;
      const rows = Array.isArray(entries) ? entries : [];
      if (rows.length === 0) {{
        head.innerHTML = '';
        body.innerHTML = '';
        return;
      }}
      const colSet = new Set();
      rows.forEach(row => Object.keys(row || {{}}).forEach(k => colSet.add(k)));
      const cols = Array.from(colSet);
      const trh = document.createElement('tr');
      cols.forEach((c) => {{
        const th = document.createElement('th');
        th.textContent = c;
        trh.appendChild(th);
      }});
      head.innerHTML = '';
      head.appendChild(trh);

      body.innerHTML = '';
      rows.forEach((row) => {{
        const tr = document.createElement('tr');
        cols.forEach((c) => {{
          const td = document.createElement('td');
          const v = row && row[c] != null ? String(row[c]) : '';
          td.textContent = v.replace(/\\n/g, ' | ');
          tr.appendChild(td);
        }});
        body.appendChild(tr);
      }});
    }}

    function parseDate(s) {{
      if (!s) return null;
      const d = new Date(String(s).replace(' ', 'T') + (String(s).includes('T') ? 'Z' : 'T00:00:00Z'));
      return Number.isNaN(d.getTime()) ? null : d;
    }}

    function setCrtShStatusLoading(show, text='') {{
      const loading = document.getElementById('crtsh-loading');
      if (show) {{
        loading.style.display = 'block';
        loading.innerHTML = `<span class="spinner"></span>${{esc(text || 'Querying crt.sh status...')}}`;
      }} else {{
        loading.style.display = 'none';
      }}
    }}

    function renderCrtShStatusFromSnapshot(snapshot) {{
      const el = document.getElementById('crtsh-status');
      const domainEl = document.getElementById('crtsh-domain');
      const latest = snapshot && snapshot.latest ? snapshot.latest : {{}};
      const cn = latest.common_name || latest.name_value || 'n/a';
      const validSince = latest.not_before || 'n/a';
      const validUntil = latest.not_after || 'n/a';
      const validity = snapshot.latest_validity || 'unknown';
      const validityClass = validity === 'valid' ? 'status-ok' : (validity.includes('expired') || validity.includes('error') ? 'status-bad' : 'status-unknown');
      const count = snapshot.match_count != null ? snapshot.match_count : (Array.isArray(snapshot.entries) ? snapshot.entries.length : 0);
      const generatedAt = snapshot.generated_at || 'n/a';
      const lastQueried = snapshot.last_queried || generatedAt;
      domainEl.textContent = snapshot.domain ? `(${{snapshot.domain}})` : '';
      el.innerHTML = `
        <p><strong>Common Name:</strong> ${{esc(cn)}}</p>
        <p><strong>Latest Generated At:</strong> ${{esc(generatedAt)}}</p>
        <p><strong>Latest Valid Since:</strong> ${{esc(validSince)}}</p>
        <p><strong>Latest Valid Until:</strong> ${{esc(validUntil)}}</p>
        <p><strong>Certificate Validity:</strong> <span class="${{validityClass}}">${{esc(validity)}}</span></p>
        <p><strong>Number of Results:</strong> ${{esc(count)}}</p>
        <p><strong>Last Queried:</strong> ${{esc(lastQueried)}}</p>
      `;
    }}

    async function loadCrtShState() {{
      setCrtShStatusLoading(true, 'Querying crt.sh status...');
      try {{
        const r = await fetch('/crtsh-state.json', {{ cache: 'no-store' }});
        const j = await r.json();
        if (j.error) {{
          setCrtShStatusLoading(false);
          renderCrtShStatusFromSnapshot({{
            domain: j.domain || meta.domain,
            generated_at: j.generated_at || 'n/a',
            latest_validity: 'error',
            match_count: 0,
            latest: {{ common_name: 'n/a', not_before: 'n/a', not_after: 'n/a' }},
          }});
          renderCrtShEntries([], `crt.sh query failed: ${{j.error}}`);
          return;
        }}
        const entries = Array.isArray(j.entries) ? j.entries : [];
        setCrtShStatusLoading(false);
        renderCrtShStatusFromSnapshot({{ ...j, last_queried: new Date().toISOString() }});
        renderCrtShEntries(
          entries,
          `domain=${{j.domain || meta.domain}}, matches=${{entries.length}}, latest_validity=${{j.latest_validity || 'unknown'}}`,
        );
      }} catch (e) {{
        setCrtShStatusLoading(false);
        renderCrtShStatusFromSnapshot({{
          domain: meta.domain,
          generated_at: 'n/a',
          latest_validity: 'error',
          match_count: 0,
          latest: {{ common_name: 'n/a', not_before: 'n/a', not_after: 'n/a' }},
        }});
        renderCrtShEntries([], `crt.sh state unavailable: ${{e.message}}`);
      }}
    }}

    async function loadCrtShLive() {{
      setCrtShStatusLoading(true, 'Querying live crt.sh via Caddy endpoint...');
      try {{
        const q = encodeURIComponent(meta.domain);
        const r = await fetch(`/probe/crtsh?q=${{q}}&output=json`, {{ cache: 'no-store' }});
        const entries = await r.json();
        const rows = Array.isArray(entries) ? entries : [];
        let latest = null;
        rows.forEach((row) => {{
          if (!latest) {{
            latest = row;
            return;
          }}
          const a = parseDate(row.not_after) || parseDate(row.entry_timestamp);
          const b = parseDate(latest.not_after) || parseDate(latest.entry_timestamp);
          if (a && b && a > b) latest = row;
        }});
        const now = new Date();
        const nb = latest ? parseDate(latest.not_before) : null;
        const na = latest ? parseDate(latest.not_after) : null;
        let validity = 'unknown';
        if (nb && na) validity = (nb <= now && now <= na) ? 'valid' : 'expired/not-yet-valid';
        else if (na) validity = now <= na ? 'valid' : 'expired';
        setCrtShStatusLoading(false);
        renderCrtShStatusFromSnapshot({{
          domain: meta.domain,
          generated_at: new Date().toISOString(),
          last_queried: new Date().toISOString(),
          latest_validity: validity,
          match_count: rows.length,
          latest: latest || {{ common_name: 'n/a', not_before: 'n/a', not_after: 'n/a' }},
        }});
        renderCrtShEntries(rows, `live crt.sh result for ${{meta.domain}} matches=${{rows.length}}`);
      }} catch (e) {{
        setCrtShStatusLoading(false);
        renderCrtShEntries([], `live crt.sh probe failed: ${{e.message}}`);
      }}
    }}

    async function refreshServicePing(svc) {{
      const el = document.getElementById(`ping-res-${{svc.name}}`);
      el.textContent = 'checking...';
      el.className = 'note';
      const res = await ping(svc.probe_url);
      const ok = res.startsWith('HTTP');
      el.textContent = res;
      el.className = ok ? 'status-ok' : 'status-bad';
    }}

    async function refreshServiceCert(svc) {{
      const el = document.getElementById(`cert-res-${{svc.name}}`);
      el.textContent = 'checking...';
      el.className = 'note';
      const res = await certCheck(svc.probe_url);
      const ok = res.includes('reachable');
      el.textContent = res;
      el.className = ok ? 'status-ok' : 'status-bad';
    }}

    function bindActions() {{
      services.forEach((svc) => {{
        document.getElementById(`ping-refresh-${{svc.name}}`).addEventListener('click', () => refreshServicePing(svc));
        document.getElementById(`cert-refresh-${{svc.name}}`).addEventListener('click', () => refreshServiceCert(svc));
        refreshServicePing(svc);
        refreshServiceCert(svc);
      }});
    }}

    function init() {{
      setMeta();
      const body = document.getElementById('svc-body');
      services.forEach(svc => body.appendChild(rowForService(svc)));
      bindActions();
      document.getElementById('crtsh-refresh-status').addEventListener('click', loadCrtShLive);
      document.getElementById('crtsh-refresh-local').addEventListener('click', loadCrtShState);
      document.getElementById('crtsh-refresh-live').addEventListener('click', loadCrtShLive);
      loadAcmeState();
      loadCrtShState();
    }}

    init();
  </script>
</body>
</html>
"""
