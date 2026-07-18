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


def render_caddy(cfg: "ReverseProxyConfig") -> str:
    """Render Caddyfile configuration from ReverseProxyConfig."""
    # Global configuration block
    global_config = textwrap.dedent(f"""
    {{
        email {json.dumps(cfg.email)}
    }}
    """).strip()

    blocks = []
    tls_block = _render_tls_block(cfg)

    # Dedicated status host with server-side probes for more reliable browser checks.
    status_lines = [
        f"status.{cfg.domain} " + "{",
        tls_block,
        "    header /probe/* Access-Control-Allow-Origin *",
        "    header /acme-state.json Access-Control-Allow-Origin *",
        "    header /crtsh-state.json Access-Control-Allow-Origin *",
        "    handle /favicon.ico {",
        "        root * /data/",
        "        file_server",
        "    }",
        "    handle_path /probe/crtsh {",
        "        reverse_proxy https://crt.sh",
        "    }",
    ]
    for upstream in cfg.upstreams:
        status_lines.append(f"    handle_path /probe/{upstream.subdomain}/* " + "{")
        status_lines.append(f"        reverse_proxy {_render_upstream_target(upstream)} " + "{")
        if upstream.forward_auth_headers:
            status_lines.append("            header_up X-Real-IP {remote_host}")
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

    # Internal root-CA distribution endpoint. The CA certificate is public
    # trust material; private keys are never exposed from this route.
    blocks.append(textwrap.dedent(f"""
    # Internal certificate distribution endpoint
    internal-ca.{cfg.domain} {{
        {tls_block}
        handle_path /cert/* {{
            root * /data/exported-certs
            file_server
        }}
        handle {{
            respond "Use /cert/caddy-internal-ca.pem or /cert/caddy-internal-ca.crt" 404
        }}
    }}
    """))

    # Wildcard convenience host
    blocks.append(textwrap.dedent(f"""
    *.{cfg.domain} {{
        {tls_block}
        root * /data/
        file_server
    }}
    """))

    # Specific upstream configurations
    for upstream in cfg.upstreams:
        block = _render_upstream_block(upstream, cfg)
        blocks.append(block)

    return "\n\n".join([global_config] + blocks)


def _render_upstream_block(upstream: "Upstream", cfg: "ReverseProxyConfig") -> str:
    """Render a single upstream configuration block."""
    rp_target = _render_upstream_target(upstream)
    block = [f"{upstream.subdomain}.{cfg.domain} " + "{"]
    block.append(_render_tls_block(cfg))
    block.append(f"    reverse_proxy {rp_target} " + "{")

    # Forward authentication headers if enabled
    if upstream.forward_auth_headers:
        block.append("        header_up X-Real-IP {remote_host}")

    # Handle HTTPS transport configuration
    if upstream.is_https:
        transport_config = _render_transport_config(upstream)
        if transport_config:
            block.append(f"        {transport_config}")

    block.append("    }")  # close reverse_proxy block
    block.append("}")  # close site block

    return "\n".join(block)


def _render_upstream_target(upstream: "Upstream") -> str:
    """Render an HTTP upstream target, including brackets for IPv6 literals."""
    host = upstream.ip
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{upstream.scheme}://{host}:{upstream.port}"


def _render_tls_block(cfg: "ReverseProxyConfig") -> str:
    """Render a DNS-01 TLS config block with tuned propagation checks."""
    return textwrap.dedent(
        f"""
        tls {{
            dns {{$CADDY_DNS_PLUGIN}} {{
                {cfg.dns_token_field} {{$CADDY_DNS_PLUGIN_TOKEN}}
            }}
            propagation_delay 60s
            propagation_timeout 15m
            resolvers 1.1.1.1 8.8.8.8
        }}
        """
    ).strip()


def _render_transport_config(upstream: "Upstream") -> str:
    """Render transport configuration for HTTPS upstreams."""
    if upstream.skip_verify:
        return "transport http { tls_insecure_skip_verify }"
    elif upstream.trust_pool:
        pool_file = Path(upstream.trust_pool).expanduser()
        return f"transport http {{ tls_trust_pool file {json.dumps(str(pool_file))} }}"
    else:
        # Use exported Caddy CA for verification
        ca_cert_path = DATADIR / "exported-certs" / "caddy-internal-ca.pem"
        return f"transport http {{ tls_trust_pool file {json.dumps(str(ca_cert_path))} }}"


def render_dnsmasq(cfg: "ReverseProxyConfig") -> str:
    """Render dnsmasq configuration from ReverseProxyConfig."""
    # Wildcard domain -> reverse-proxy host IP
    target_ip = getattr(cfg, "dnsmasq_address_ip", "10.0.0.1")
    return textwrap.dedent(f"""
    no-resolv
    log-queries
    log-facility=/data/logs/dnsmasq.log
    address=/.{cfg.domain}/{target_ip}
    """).lstrip()


def render_upstream_tls_setup_guide(cert_info: dict) -> str:
    """Render the upstream TLS setup guide markdown content."""
    import time

    return f"""# Upstream TLS Configuration

## Caddy Internal Certificate Export

Caddy's internal root CA has been exported to:
- **PEM format**: `{cert_info['ca_cert_pem']}`
- **CRT format**: `{cert_info['ca_cert_crt']}`

## Certificate Expiration Notice

The actual CA lifetime depends on the Caddy version and PKI configuration.
Inspect the exported certificate rather than relying on a fixed assumed lifetime:

```bash
openssl x509 -in {cert_info['ca_cert_pem']} -noout -subject -issuer -dates -fingerprint -sha256
```

When the root CA changes or approaches expiry, redistribute the new certificate
and update every dependent trust store.

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
    """Render the accessible operational status dashboard."""
    from .status_page import render_status_page

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
    return render_status_page(
        _json_for_inline_script(services),
        _json_for_inline_script(public_meta),
    )

def _json_for_inline_script(value: object) -> str:
    """Serialize JSON without allowing values to terminate the script element."""
    return (
        json.dumps(value)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
