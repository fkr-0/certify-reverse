#!/usr/bin/env python3
"""
Template rendering functions for Caddy and dnsmasq configurations.

This module contains all templating logic separated from the main application logic.
"""
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app import ReverseProxyConfig, Upstream

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
