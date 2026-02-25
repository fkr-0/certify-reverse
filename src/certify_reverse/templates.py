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
        
        # Internal CA for issuing certificates to internal services
        pki {{
            ca internal {{
                name "Caddy Internal CA"
                root_cn "Caddy Internal Root CA"
                intermediate_cn "Caddy Internal Intermediate CA"
                root_ca_ttl 24h * 365 * 25  # 25 years
                intermediate_ca_ttl 24h * 365 * 5  # 5 years
                # Monitor expiration: caddy pki ca list
            }}
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
    ]
    for upstream in cfg.upstreams:
        status_lines.append(f"    handle_path /probe/{upstream.subdomain}/* " + "{")
        status_lines.append(
            f"        reverse_proxy {upstream.scheme}://{upstream.ip}:{upstream.port} " + "{"
        )
        if upstream.forward_auth_headers:
            status_lines.append("            header_up X-Forwarded-Host {host}")
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
        block.append("        header_up X-Forwarded-Host {host}")
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
    # Wildcard domain -> proxy host (assumed 10.0.0.1, change as needed)
    return textwrap.dedent(
        f"""
    no-resolv
    log-queries
    log-facility=/var/log/dnsmasq.log
    address=/.{cfg.domain}/10.0.0.1
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
    .note {{ color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>certify-reverse Dashboard</h1>
      <div class="meta" id="meta"></div>
    </div>
    <div class="card">
      <h2>Services</h2>
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Public URL</th>
            <th>Upstream Target</th>
            <th>Status</th>
            <th>Actions</th>
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
  </div>
  <script>
    const services = {services_json};
    const meta = {meta_json};

    function esc(s) {{
      return String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
    }}

    function setMeta() {{
      const el = document.getElementById('meta');
      el.innerHTML = `
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
        <td id="st-${{esc(svc.name)}}">unknown</td>
        <td>
          <button class="btn" id="ping-${{esc(svc.name)}}">Ping</button>
          <button class="btn" id="cert-${{esc(svc.name)}}">Check Cert</button>
        </td>
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

    function bindActions() {{
      services.forEach((svc) => {{
        const st = document.getElementById(`st-${{svc.name}}`);
        document.getElementById(`ping-${{svc.name}}`).addEventListener('click', async () => {{
          st.textContent = 'checking...';
          const res = await ping(svc.probe_url);
          const ok = res.startsWith('HTTP');
          st.textContent = res;
          st.className = ok ? 'status-ok' : 'status-bad';
        }});
        document.getElementById(`cert-${{svc.name}}`).addEventListener('click', async () => {{
          st.textContent = 'checking tls...';
          const res = await certCheck(svc.probe_url);
          const ok = res.includes('reachable');
          st.textContent = res;
          st.className = ok ? 'status-ok' : 'status-bad';
        }});
      }});
    }}

    function init() {{
      setMeta();
      const body = document.getElementById('svc-body');
      services.forEach(svc => body.appendChild(rowForService(svc)));
      bindActions();
      loadAcmeState();
    }}

    init();
  </script>
</body>
</html>
"""
