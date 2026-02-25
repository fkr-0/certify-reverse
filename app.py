#!/usr/bin/env python3
"""
Runtime bootstrapper for Caddy with custom DNS-01 plug-in.

Steps
1. Read config.yml  → ReverseProxyConfig (pydantic-like dataclass)
2. Ensure Caddy binary with requested dns.providers.<dns_provider>
3. Render:
      • /data/Caddyfile
      • /data/dnsmasq.conf
4. Run trust-pool extension(s) if needed (issue / renew)
5. Exec Caddy (PID 1) – graceful reloads via SIGHUP

No external Python dependencies – only stdlib.
"""
from __future__ import annotations

import argparse
import importlib
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml

# Import templating functions
from templates import (
    render_caddy,
    render_dnsmasq,
    render_upstream_tls_setup_guide,
    set_datadir,
)

# ---------------------------------------------------------------------
# configurable paths - all generated files go to /data for persistence
BASE = Path("/")
CFG = BASE / "config.yml"
DATADIR = Path("/data")
DATADIR.mkdir(parents=True, exist_ok=True)

# All generated files in /data for persistence and organization
CADDY = DATADIR / "caddy-rebuild"
WORK = DATADIR / "caddybuild"
CFILE = DATADIR / "Caddyfile"
DNSMASQ = DATADIR / "dnsmasq.conf"
LOGDIR = DATADIR / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# logging - dual output to stdout and /data/logs/
LOGFMT = "%(asctime)s [%(levelname)s] %(message)s"
log = logging.getLogger("bootstrap")
log.setLevel(logging.DEBUG)

# File logging with rotation
_rot = RotatingFileHandler(LOGDIR / "app.log", maxBytes=100_000, backupCount=5)
_rot.setFormatter(logging.Formatter(LOGFMT))
log.addHandler(_rot)

# Console logging for stdout
_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(logging.Formatter(LOGFMT))
log.addHandler(_console)

# Ensure all log messages go to both outputs
log.info("Logging initialized - output to stdout and %s", LOGDIR / "app.log")


# ---------------------------------------------------------------------
# helpers
def run(cmd: list[str] | str, **kw):
    """Run a shell command, raise RuntimeError on failure, return stdout."""
    if isinstance(cmd, str):
        cmd = cmd.split()
    log.debug("+ %s", " ".join(cmd))
    try:
        out = subprocess.check_output(cmd, text=True, **kw)
        return out
    except subprocess.CalledProcessError as e:
        log.error("Command failed [%s]: %s", e.returncode, e)
        raise RuntimeError from e


def which(path: Path):
    return shutil.which(str(path)) or path


# ---------------------------------------------------------------------
# dataclasses representing config.yml
@dataclass(slots=True)
class Upstream:
    subdomain: str
    ip: str
    port: int
    scheme: str = "http"  # "http" | "https"
    skip_verify: bool = False
    trust_pool: str | None = None  # path to root CA to trust
    forward_auth_headers: bool = True
    ext_name: str | None = None  # trust-pool extension name
    ext_params: dict = field(default_factory=dict)

    @property
    def is_https(self):
        return self.scheme == "https"


@dataclass(slots=True)
class ReverseProxyConfig:
    dns_provider: str
    dns_token: str
    email: str
    domain: str
    upstreams: list[Upstream]

    @classmethod
    def from_file(cls, p: Path):
        data = yaml.safe_load(p.read_text())
        ups = [Upstream(**u) for u in data["upstreams"]]
        return cls(
            dns_provider=data["dns_provider"],
            dns_token=data["dns_token"],
            email=data.get("email", "admin@example.com"),
            domain=data["domain"],
            upstreams=ups,
        )


# ---------------------------------------------------------------------
# caddy build / inspection
def caddy_has_plugin(provider: str) -> bool:
    if not CADDY.exists():
        return False
    mods = run([str(CADDY), "list-modules"]).splitlines()
    return any(provider in m for m in mods)


def build_caddy(dns_provider: str):
    """Build Caddy with the configured DNS provider plugin."""
    log.info("Building Caddy with dns.providers.%s ...", dns_provider)
    if CADDY.exists():
        log.info("Removing existing Caddy binary at %s ...", CADDY)
        CADDY.unlink()
    env = os.environ.copy()
    # Allow Go to fetch a newer toolchain when module requirements demand it.
    env.setdefault("GOTOOLCHAIN", "auto")
    run(
        [
            "xcaddy",
            "build",
            "latest",
            "--with",
            f"github.com/caddy-dns/{dns_provider}",
            "--output",
            str(CADDY),
        ],
        env=env,
        cwd=WORK,
    )


def get_caddy_certificates() -> dict:
    """Retrieve internal certificates from Caddy."""
    if not CADDY.exists():
        raise RuntimeError("Caddy binary not found")

    try:
        # Get the current config in JSON format to extract certificate info
        config_json = run(
            [str(CADDY), "config", "--adapter", "caddyfile", "--config", str(CFILE)]
        )
        config_data = yaml.safe_load(config_json)

        # Extract certificate information
        certs_info = {
            "certificates": [],
            "ca_certificates": [],
            "timestamp": time.time(),
        }

        # Navigate the JSON structure to find certificate data
        if "apps" in config_data and "tls" in config_data["apps"]:
            tls_app = config_data["apps"]["tls"]

            # Get certificates from automation policies
            if "automation" in tls_app and "policies" in tls_app["automation"]:
                for policy in tls_app["automation"]["policies"]:
                    if "subjects" in policy and isinstance(policy["subjects"], list):
                        certs_info["certificates"].extend(policy["subjects"])

            # Get certificate stores
            if "certificates" in tls_app:
                cert_stores = tls_app["certificates"]
                for store_name, store_data in cert_stores.items():
                    if isinstance(store_data, list):
                        for cert in store_data:
                            if "certificate" in cert:
                                certs_info["ca_certificates"].append(
                                    {
                                        "store": store_name,
                                        "certificate": cert.get("certificate", ""),
                                        "key": cert.get("key", ""),
                                    }
                                )

        return certs_info

    except Exception as e:
        log.error("Failed to retrieve certificates: %s", e)
        raise RuntimeError(f"Certificate retrieval failed: {e}") from e


def print_certificates():
    """Print certificate information in a readable format."""
    try:
        certs = get_caddy_certificates()

        print("=== Caddy Internal Certificates ===")
        print(f"Retrieved at: {time.ctime(certs['timestamp'])}")
        print()

        if certs["certificates"]:
            print("Managed Certificates:")
            for i, cert in enumerate(certs["certificates"], 1):
                print(f"  {i}. {cert}")
            print()
        else:
            print("No managed certificates found.")
            print()

        if certs["ca_certificates"]:
            print("CA Certificates:")
            for i, ca_cert in enumerate(certs["ca_certificates"], 1):
                print(f"  {i}. Store: {ca_cert['store']}")
                if ca_cert["certificate"]:
                    cert_preview = (
                        ca_cert["certificate"][:100] + "..."
                        if len(ca_cert["certificate"]) > 100
                        else ca_cert["certificate"]
                    )
                    print(f"     Certificate: {cert_preview}")
                print()
        else:
            print("No CA certificates found.")

    except Exception as e:
        print(f"Error retrieving certificates: {e}")
        sys.exit(1)


def export_caddy_internal_certs():
    """Export Caddy's internal root CA certificate for upstream TLS validation."""
    if not CADDY.exists():
        raise RuntimeError("Caddy binary not found")

    cert_export_dir = DATADIR / "exported-certs"
    cert_export_dir.mkdir(parents=True, exist_ok=True)

    try:
        log.info("Exporting Caddy internal certificates for upstream TLS...")

        # Get Caddy's internal root CA
        ca_cert_output = run([str(CADDY), "trust", "ca", "--format", "pem"])

        # Write root CA certificate
        ca_cert_path = cert_export_dir / "caddy-internal-ca.pem"
        ca_cert_path.write_text(ca_cert_output)
        log.info("Exported Caddy internal root CA → %s", ca_cert_path)

        # Also export in different formats for compatibility
        ca_cert_crt_path = cert_export_dir / "caddy-internal-ca.crt"
        ca_cert_crt_path.write_text(ca_cert_output)
        log.info("Exported Caddy internal root CA (CRT format) → %s", ca_cert_crt_path)

        return {
            "ca_cert_pem": str(ca_cert_path),
            "ca_cert_crt": str(ca_cert_crt_path),
            "export_dir": str(cert_export_dir),
        }

    except Exception as e:
        log.error("Failed to export Caddy internal certificates: %s", e)
        raise RuntimeError(f"Certificate export failed: {e}") from e


def auto_export_internal_ca():
    """Automatically export internal CA certificate from Caddy's PKI storage."""
    cert_export_dir = DATADIR / "exported-certs"
    cert_export_dir.mkdir(parents=True, exist_ok=True)

    try:
        log.info("Auto-exporting Caddy internal CA certificate...")

        # Method 1: Try to get the CA from Caddy's PKI storage directory
        # Caddy stores PKI data in the data directory under pki/
        pki_dirs = [
            DATADIR / "pki" / "ca" / "internal",
            DATADIR / "pki" / "authorities" / "internal",
            DATADIR / "caddy" / "pki" / "authorities" / "internal",
        ]

        ca_source_path = None
        for pki_dir in pki_dirs:
            if pki_dir.exists():
                # Look for the root certificate files
                possible_ca_files = [
                    "root.crt",
                    "ca.crt",
                    "root.pem",
                    "ca.pem",
                    "intermediate.crt",
                    "intermediate.pem",
                ]

                for filename in possible_ca_files:
                    ca_path = pki_dir / filename
                    if ca_path.exists() and ca_path.stat().st_size > 0:
                        ca_source_path = ca_path
                        log.info("Found CA certificate at: %s", ca_path)
                        break

                if ca_source_path:
                    break

        if ca_source_path:
            # Copy to standard export location
            ca_cert_pem_path = cert_export_dir / "caddy-internal-ca.pem"
            ca_cert_crt_path = cert_export_dir / "caddy-internal-ca.crt"

            # Read and write to ensure proper format
            ca_content = ca_source_path.read_text()
            ca_cert_pem_path.write_text(ca_content)
            ca_cert_crt_path.write_text(ca_content)

            log.info(
                "Auto-exported Caddy internal CA from storage → %s", ca_cert_pem_path
            )

            return {
                "ca_cert_pem": str(ca_cert_pem_path),
                "ca_cert_crt": str(ca_cert_crt_path),
                "export_dir": str(cert_export_dir),
                "source": "storage",
            }

        # Method 2: Try using caddy trust command (if Caddy binary exists)
        if CADDY.exists():
            try:
                log.info("Trying 'caddy trust ca' command...")
                ca_cert_output = run([str(CADDY), "trust", "ca", "--format", "pem"])

                if (
                    ca_cert_output and len(ca_cert_output) > 100
                ):  # Sanity check for valid cert
                    ca_cert_pem_path = cert_export_dir / "caddy-internal-ca.pem"
                    ca_cert_crt_path = cert_export_dir / "caddy-internal-ca.crt"

                    ca_cert_pem_path.write_text(ca_cert_output)
                    ca_cert_crt_path.write_text(ca_cert_output)

                    log.info(
                        "Exported Caddy internal CA via command → %s", ca_cert_pem_path
                    )

                    return {
                        "ca_cert_pem": str(ca_cert_pem_path),
                        "ca_cert_crt": str(ca_cert_crt_path),
                        "export_dir": str(cert_export_dir),
                        "source": "command",
                    }
            except Exception as cmd_error:
                log.debug("caddy trust command failed: %s", cmd_error)

        # Method 3: Check if certificates were already exported
        existing_pem = cert_export_dir / "caddy-internal-ca.pem"
        existing_crt = cert_export_dir / "caddy-internal-ca.crt"

        if existing_pem.exists() and existing_pem.stat().st_size > 100:
            log.info("Using existing exported CA certificate: %s", existing_pem)
            return {
                "ca_cert_pem": str(existing_pem),
                "ca_cert_crt": str(existing_crt),
                "export_dir": str(cert_export_dir),
                "source": "existing",
            }

        log.info(
            "CA certificate not yet available - will be available after Caddy initializes PKI"
        )
        return None

    except Exception as e:
        log.warning("Failed to auto-export internal CA: %s", e)
        return None


def generate_internal_service_certs(cfg: ReverseProxyConfig):
    """Generate certificates for internal services using Caddy's internal CA."""
    service_certs_dir = DATADIR / "service-certs"
    service_certs_dir.mkdir(parents=True, exist_ok=True)

    log.info("Generating internal service certificates...")

    for upstream in cfg.upstreams:
        if upstream.is_https:
            service_name = f"{upstream.subdomain}.{cfg.domain}"
            cert_path = service_certs_dir / f"{upstream.subdomain}"
            cert_path.mkdir(parents=True, exist_ok=True)

            try:
                # Generate certificate using Caddy's internal CA
                log.info("Generating certificate for %s", service_name)

                # Use Caddy's PKI to generate certificates
                cert_output = run(
                    [
                        str(CADDY),
                        "pki",
                        "certificate",
                        "--ca",
                        "internal",
                        "--host",
                        service_name,
                        "--host",
                        upstream.ip,  # Include IP as SAN
                        "--out-cert",
                        str(cert_path / "cert.pem"),
                        "--out-key",
                        str(cert_path / "key.pem"),
                    ]
                )

                log.info("Generated certificate for %s → %s", service_name, cert_path)

            except Exception as e:
                log.error("Failed to generate certificate for %s: %s", service_name, e)
                continue


def auto_export_ca_certificates(cfg: "ReverseProxyConfig" = None):
    """Automatically export CA certificates after Caddy PKI initialization and copy to service directories."""
    try:
        log.info("🔐 Starting automatic CA certificate export process...")

        # First, export the main CA certificates
        export_caddy_internal_certs()
        log.info("✅ Main CA certificate export completed successfully")

        # If config is provided, copy CA certificates to individual service directories
        if cfg:
            copy_ca_to_service_directories(cfg)
        else:
            log.warning(
                "⚠️ No configuration provided - skipping service-specific CA copies"
            )

    except Exception as e:
        log.warning(
            "⚠️ Automatic CA export failed (this is normal on first startup): %s", e
        )
        log.info("💡 CA certificates will be available after Caddy PKI initializes")


def copy_ca_to_service_directories(cfg: ReverseProxyConfig):
    """Copy CA certificate to individual service directories for easy mounting."""
    try:
        log.info("📁 Creating service-specific CA certificate directories...")

        # Ensure the main exported certs exist
        main_ca_pem = DATADIR / "exported-certs" / "caddy-internal-ca.pem"
        main_ca_crt = DATADIR / "exported-certs" / "caddy-internal-ca.crt"

        if not main_ca_pem.exists():
            log.warning(
                "⚠️ Main CA certificate not found at %s - cannot copy to service directories",
                main_ca_pem,
            )
            return

        log.info("📋 Found %d upstream services in configuration", len(cfg.upstreams))

        # Create service directories and copy CA certificates
        services_processed = 0
        for upstream in cfg.upstreams:
            service_name = upstream.subdomain
            service_dir = DATADIR / service_name

            log.info("📂 Processing service: %s", service_name)

            try:
                # Create service directory
                service_dir.mkdir(parents=True, exist_ok=True)
                log.debug("✅ Created/verified directory: %s", service_dir)

                # Copy PEM format
                service_ca_pem = service_dir / "caddy-internal-ca.pem"
                import shutil

                shutil.copy2(main_ca_pem, service_ca_pem)
                log.debug(
                    "📄 Copied PEM certificate: %s → %s", main_ca_pem, service_ca_pem
                )

                # Copy CRT format
                service_ca_crt = service_dir / "caddy-internal-ca.crt"
                shutil.copy2(main_ca_crt, service_ca_crt)
                log.debug(
                    "📄 Copied CRT certificate: %s → %s", main_ca_crt, service_ca_crt
                )

                # Set appropriate permissions (readable by all, writable by owner)
                service_ca_pem.chmod(0o644)
                service_ca_crt.chmod(0o644)
                log.debug(
                    "🔒 Set permissions (644) for certificates in %s", service_dir
                )

                # Create a README file for the service
                import time

                readme_content = f"""# CA Certificate for {service_name}

This directory contains the Caddy Internal CA certificate for the {service_name} service.

## Files:
- `caddy-internal-ca.pem` - PEM format CA certificate
- `caddy-internal-ca.crt` - CRT format CA certificate (same content, different extension)

## Usage in Docker:
```yaml
services:
  {service_name}:
    volumes:
      - ./caddy-data/{service_name}:/etc/ssl/caddy:ro
    environment:
      - SSL_CERT_FILE=/etc/ssl/caddy/caddy-internal-ca.pem
      - CADDY_CA_CERT=/etc/ssl/caddy/caddy-internal-ca.pem
```

## Service Configuration:
- Subdomain: {service_name}.{cfg.domain}
- Target: {upstream.scheme}://{upstream.ip}:{upstream.port}
- HTTPS Backend: {"Yes" if upstream.is_https else "No"}

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
                readme_path = service_dir / "README.md"
                readme_path.write_text(readme_content)
                log.debug("📝 Created README.md in %s", service_dir)

                services_processed += 1
                log.info(
                    "✅ Service %s: CA certificates copied successfully", service_name
                )

            except Exception as e:
                log.error("❌ Failed to process service %s: %s", service_name, e)
                continue

        log.info(
            "🎉 CA certificate copying completed: %d/%d services processed successfully",
            services_processed,
            len(cfg.upstreams),
        )

        # Log the directory structure for verification
        log.info("📁 Service directories created:")
        for upstream in cfg.upstreams:
            service_dir = DATADIR / upstream.subdomain
            if service_dir.exists():
                files = list(service_dir.iterdir())
                log.info(
                    "  📂 /%s (%d files): %s",
                    upstream.subdomain,
                    len(files),
                    [f.name for f in files],
                )

    except Exception as e:
        log.error("❌ Failed to copy CA certificates to service directories: %s", e)
        raise


def run_extensions(cfg: ReverseProxyConfig):
    for u in cfg.upstreams:
        if not u.is_https or not u.trust_pool or not u.ext_name:
            continue
        try:
            mod = importlib.import_module(f"trust_ext.{u.ext_name}")
            ExtCls = getattr(mod, "TrustExtension")
            ext = ExtCls(**u.ext_params)
            if not ext.status(u):
                log.info("Issuing certificate for %s via %s", u.subdomain, u.ext_name)
                ext.issue(u)
            else:
                log.debug(
                    "Certificate for %s ok – expires %s", u.subdomain, ext.status(u)
                )
        except Exception as e:
            log.error("Extension %s failed on %s: %s", u.ext_name, u.subdomain, e)


# ---------------------------------------------------------------------
def main(force: bool = False, show_certs: bool = False):
    # Handle certificate retrieval mode
    if show_certs:
        print_certificates()
        return

    # Set the datadir for templates module
    set_datadir(DATADIR)

    cfg = ReverseProxyConfig.from_file(CFG)
    log.info(
        "Loaded config for domain %s with %d upstream(s)",
        cfg.domain,
        len(cfg.upstreams),
    )

    # build Caddy if needed
    if force or not CADDY.exists() or not caddy_has_plugin(cfg.dns_provider):
        build_caddy(cfg.dns_provider)
    else:
        log.info("Existing Caddy binary has the dns provider – skipping rebuild")

    # trust extension workflow (before rendering Caddyfile)
    run_extensions(cfg)

    # render configs
    CFILE.write_text(render_caddy(cfg))
    log.info("Wrote Caddyfile → %s", CFILE)
    DNSMASQ.write_text(render_dnsmasq(cfg))
    log.info("Wrote dnsmasq.conf → %s", DNSMASQ)

    # option: install local root CA into host store
    try:
        run([str(CADDY), "trust", "--disable-tls-verification"])
        log.info("Executed 'caddy trust' (may be NOP under Docker)")
    except RuntimeError:
        log.warning("caddy trust failed – likely running as non-root")

    # auto-export internal CA certificate for immediate availability
    try:
        cert_info = auto_export_internal_ca()
        if cert_info:
            log.info("Auto-exported Caddy internal CA certificate immediately")
            # Generate setup guide with the exported cert info
            instructions_path = DATADIR / "upstream-tls-setup.md"
            instructions_content = render_upstream_tls_setup_guide(cert_info)
            instructions_path.write_text(instructions_content)
            log.info("Created upstream TLS setup guide → %s", instructions_path)
        else:
            log.info(
                "CA certificate not yet available, will monitor after Caddy startup"
            )
    except Exception as e:
        log.warning("Failed to auto-export CA certificate: %s", e)

    # Auto-export CA certificates and copy to service directories
    try:
        auto_export_ca_certificates(cfg)
        log.info("✅ Auto-exported CA certificates and created service directories")
    except Exception as e:
        log.warning("⚠️ Failed to auto-export CA certificates: %s", e)

    # generate service certificates for internal HTTPS services
    try:
        generate_internal_service_certs(cfg)
        log.info("Generated internal service certificates")
    except RuntimeError as e:
        log.warning("Failed to generate service certificates: %s", e)

    # Note: CA certificate will be auto-exported after Caddy starts
    # Users can also manually export with: ./caddy-docker.sh app --export-certs
    log.info("CA certificate will be available after Caddy initializes PKI")

    # finally exec Caddy (PID1)
    log.info("Starting Caddy …")
    os.execvp(
        str(CADDY),
        [str(CADDY), "run", "--config", str(CFILE), "--adapter", "caddyfile"],
    )


# ---------------------------------------------------------------------
if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    arg = argparse.ArgumentParser(
        description="Caddy DNS-01 bootstrapper with certificate management",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    arg.add_argument(
        "--force-build", action="store_true", help="Rebuild Caddy even if binary exists"
    )
    arg.add_argument(
        "--show-certs",
        action="store_true",
        help="Retrieve and display Caddy internal certificates, then exit",
    )
    arg.add_argument(
        "--export-certs",
        action="store_true",
        help="Export Caddy internal root CA for upstream TLS validation, then exit",
    )
    arg.add_argument(
        "--create-service-dirs",
        action="store_true",
        help="Create service-specific CA certificate directories based on config.yml, then exit",
    )

    opts = arg.parse_args()

    # Handle certificate export mode
    if opts.export_certs:
        try:
            cert_info = export_caddy_internal_certs()

            # Create setup instructions
            instructions_path = DATADIR / "upstream-tls-setup.md"
            instructions_content = render_upstream_tls_setup_guide(cert_info)
            instructions_path.write_text(instructions_content)

            print(f"✅ Exported Caddy internal certificates:")
            print(f"   CA Certificate (PEM): {cert_info['ca_cert_pem']}")
            print(f"   CA Certificate (CRT): {cert_info['ca_cert_crt']}")
            print(f"   Export Directory: {cert_info['export_dir']}")
            print(f"   Setup Guide: {instructions_path}")
        except Exception as e:
            print(f"❌ Failed to export certificates: {e}")
            sys.exit(1)
        sys.exit(0)

    # Handle service directory creation mode
    if opts.create_service_dirs:
        try:
            cfg = ReverseProxyConfig.from_file(CFG)
            auto_export_ca_certificates(cfg)
            print(f"✅ Created service-specific CA certificate directories:")
            for upstream in cfg.upstreams:
                service_dir = DATADIR / upstream.subdomain
                if service_dir.exists():
                    print(f"   📂 {service_dir} (subdomain: {upstream.subdomain})")
        except Exception as e:
            print(f"❌ Failed to create service directories: {e}")
            sys.exit(1)
        sys.exit(0)

    main(force=opts.force_build, show_certs=opts.show_certs)


def monitor_and_export_ca():
    """Monitor for CA certificate availability and export when ready."""
    max_attempts = 30  # Try for 30 seconds
    attempt = 0

    while attempt < max_attempts:
        cert_info = auto_export_internal_ca()
        if cert_info:
            log.info(
                "Successfully exported CA certificate after %d attempts", attempt + 1
            )
            # Generate setup guide
            try:
                instructions_path = DATADIR / "upstream-tls-setup.md"
                instructions_content = render_upstream_tls_setup_guide(cert_info)
                instructions_path.write_text(instructions_content)
                log.info("Created upstream TLS setup guide → %s", instructions_path)
            except Exception as e:
                log.warning("Failed to create setup guide: %s", e)
            return cert_info

        attempt += 1
        time.sleep(1)  # Wait 1 second between attempts

    log.warning("Failed to export CA certificate after %d attempts", max_attempts)
    return None
