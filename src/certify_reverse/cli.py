#!/usr/bin/env python3
"""
Runtime bootstrapper for Caddy with DNS plugin build support.

Configuration model:
- /config/.env for global settings (DNS provider/token/domain/email/caddy version)
- /config/upstreams.yml for upstream definitions (top-level keys are subdomains)
"""
from __future__ import annotations

import argparse
import difflib
import importlib
import importlib.metadata
import importlib.resources
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import yaml

from .templates import (
    render_caddy,
    render_dnsmasq,
    render_status_index_html,
    render_upstream_tls_setup_guide,
    set_datadir,
)

BASE = Path("/")
CONFIG_DIR = BASE / "config"
ENV_FILE = CONFIG_DIR / ".env"
UPSTREAMS_FILE = CONFIG_DIR / "upstreams.yml"
DATADIR = Path("/data")

CADDY = DATADIR / "caddy-rebuild"
WORK = DATADIR / "caddybuild"
CFILE = DATADIR / "Caddyfile"
CFILE_OVERWRITE = DATADIR / "Caddyfile.overwrite"
DNSMASQ = DATADIR / "dnsmasq.conf"
INDEX_HTML = DATADIR / "index.html"
ACME_STATE_JSON = DATADIR / "acme-state.json"
CRTSH_STATE_JSON = DATADIR / "crtsh-state.json"
LOGDIR = DATADIR / "logs"

LOGFMT = "%(asctime)s [%(levelname)s] %(message)s"
log = logging.getLogger("bootstrap")
log.setLevel(logging.DEBUG)
_LOG_CONFIGURED = False
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_C_HL = "\033[96m"
_C_OK = "\033[92m"
_C_WARN = "\033[93m"
_C_RESET = "\033[0m"


class StripAnsiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        return _ANSI_RE.sub("", s)


class InvalidSetupError(Exception):
    """Raised when required configuration is missing or malformed."""


def hl(value: Any) -> str:
    return f"{_C_HL}{value}{_C_RESET}"


def configure_logging() -> None:
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return

    file_logging_ready = True
    try:
        DATADIR.mkdir(parents=True, exist_ok=True)
        LOGDIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        file_logging_ready = False

    if file_logging_ready:
        rot = RotatingFileHandler(LOGDIR / "app.log", maxBytes=100_000, backupCount=5)
        rot.setFormatter(StripAnsiFormatter(LOGFMT))
        log.addHandler(rot)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOGFMT))
    log.addHandler(console)

    _LOG_CONFIGURED = True
    if file_logging_ready:
        log.info("Logging initialized - output to stdout and %s", LOGDIR / "app.log")
    else:
        log.warning("Logging initialized in console-only mode (cannot write %s)", LOGDIR)


@dataclass(slots=True)
class Upstream:
    subdomain: str
    ip: str
    port: int
    scheme: str = "http"
    skip_verify: bool = False
    trust_pool: str | None = None
    forward_auth_headers: bool = True
    ext_name: str | None = None
    ext_params: dict[str, Any] = field(default_factory=dict)

    @property
    def is_https(self) -> bool:
        return self.scheme.lower() == "https"


@dataclass(slots=True)
class ReverseProxyConfig:
    dns_provider: str
    dns_token: str
    email: str
    domain: str
    caddy_version: str = "latest"
    dnsmasq_address_mode: str = "manual"
    dnsmasq_address_ip: str = "10.0.0.1"
    upstreams: list[Upstream] = field(default_factory=list)

    @classmethod
    def from_sources(cls) -> "ReverseProxyConfig":
        load_env_file(ENV_FILE)

        dns_provider = must_env("DNS_PROVIDER")
        dns_token = must_env("DNS_TOKEN")
        email = os.getenv("ACME_EMAIL", "admin@example.com")
        domain = must_env("DOMAIN")
        caddy_version = os.getenv("CADDY_VERSION", "latest").strip() or "latest"
        dnsmasq_address_mode = env_first(
            "DNSMASQ_ADDRESS_MODE",
            "dnsmasq_address_mode",
            default="manual",
        ).lower()
        manual_dnsmasq_ip = env_first("DNSMASQ_ADDRESS_IP", "dnsmasq_address_ip", default="10.0.0.1")
        dnsmasq_address_ip = derive_dnsmasq_address_ip(dnsmasq_address_mode, manual_dnsmasq_ip)

        upstreams = load_upstreams(UPSTREAMS_FILE)
        return cls(
            dns_provider=dns_provider,
            dns_token=dns_token,
            email=email,
            domain=domain,
            caddy_version=caddy_version,
            dnsmasq_address_mode=dnsmasq_address_mode,
            dnsmasq_address_ip=dnsmasq_address_ip,
            upstreams=upstreams,
        )


def run(cmd: list[str] | str, **kw) -> str:
    if isinstance(cmd, str):
        cmd = cmd.split()
    log.debug("+ %s", " ".join(cmd))
    try:
        return subprocess.check_output(cmd, text=True, **kw)
    except subprocess.CalledProcessError as e:
        log.error("Command failed [%s]: %s", e.returncode, e)
        raise RuntimeError from e


def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise InvalidSetupError(f"Missing required environment variable: {name}")
    return v


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        v = os.getenv(name)
        if v is not None and v.strip():
            return v.strip()
    return default


def is_ipv4(value: str) -> bool:
    return bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", value))


def resolve_hostname_ipv4(name: str) -> str | None:
    try:
        return socket.gethostbyname(name)
    except Exception:
        return None


def _extract_src_ip_from_route(route_output: str) -> str | None:
    m = re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)\b", route_output)
    return m.group(1) if m else None


def derive_dnsmasq_address_ip(mode: str, manual_ip: str) -> str:
    host_derived = env_first("HOST_DNSMASQ_ADDRESS_IP", default="")
    if mode in {"host-src-ip", "auto"} and host_derived and is_ipv4(host_derived):
        log.info(
            "dnsmasq address mode=%s using host-derived src IP=%s",
            hl(mode),
            hl(host_derived),
        )
        return host_derived

    if manual_ip and not is_ipv4(manual_ip):
        resolved = resolve_hostname_ipv4(manual_ip)
        if resolved:
            log.info(
                "Resolved DNSMASQ_ADDRESS_IP hostname %s -> %s",
                hl(manual_ip),
                hl(resolved),
            )
            manual_ip = resolved

    if mode not in {"manual", "host-src-ip", "auto"}:
        log.warning("Unknown DNSMASQ_ADDRESS_MODE=%s; falling back to manual", hl(mode))
        return manual_ip
    if mode == "manual":
        log.info("dnsmasq address mode=%s target=%s", hl(mode), hl(manual_ip))
        return manual_ip

    try:
        route = subprocess.check_output(
            ["ip", "-4", "route", "get", "1.1.1.1"],
            text=True,
            stderr=subprocess.STDOUT,
        )
        detected = _extract_src_ip_from_route(route)
        if detected:
            log.info(
                "dnsmasq address mode=%s detected host src IP=%s",
                hl(mode),
                hl(detected),
            )
            return detected
        log.warning(
            "Could not parse src IP from 'ip route get' output; using manual DNSMASQ_ADDRESS_IP=%s",
            hl(manual_ip),
        )
    except Exception as e:
        log.warning(
            "Failed to derive host src IP (%s); using manual DNSMASQ_ADDRESS_IP=%s",
            e,
            hl(manual_ip),
        )
    log.info("dnsmasq address mode=%s fallback target=%s", hl(mode), hl(manual_ip))
    return manual_ip


def load_env_file(path: Path) -> None:
    if not path.exists():
        log.warning("%s not found; relying on process environment", path)
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        # File-based runtime config is authoritative for this app and must
        # override inherited image/base environment defaults.
        os.environ[k] = v


def load_upstreams(path: Path) -> list[Upstream]:
    if not path.exists():
        raise InvalidSetupError(
            f"Missing upstreams file: {path}. Copy upstreams.yml.example to upstreams.yml."
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise InvalidSetupError("upstreams.yml must contain a top-level mapping")

    upstreams: list[Upstream] = []
    for subdomain, spec in data.items():
        if not isinstance(spec, dict):
            raise InvalidSetupError(f"Upstream '{subdomain}' must be an object")
        upstreams.append(Upstream(subdomain=subdomain, **spec))

    return upstreams


def semver_tuple(version: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def get_built_caddy_version() -> str:
    if not CADDY.exists():
        return "not-built"
    try:
        return run([str(CADDY), "version"]).strip()
    except Exception:
        return "unknown"


def get_latest_caddy_version() -> str:
    req = Request(
        "https://api.github.com/repos/caddyserver/caddy/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "certify-reverse"},
    )
    with urlopen(req, timeout=10) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return str(payload.get("tag_name", "unknown"))


def check_caddy_update_status() -> dict[str, Any]:
    built = get_built_caddy_version()
    native_upgrade_supported = False
    if CADDY.exists():
        try:
            run([str(CADDY), "upgrade", "--help"])
            native_upgrade_supported = True
        except Exception:
            native_upgrade_supported = False
    try:
        latest = get_latest_caddy_version()
    except URLError as e:
        return {
            "built": built,
            "latest": "unavailable",
            "recommended": None,
            "native_upgrade_supported": native_upgrade_supported,
            "error": str(e),
        }

    bt = semver_tuple(built)
    lt = semver_tuple(latest)
    recommended = bool(bt and lt and bt < lt)
    return {
        "built": built,
        "latest": latest,
        "recommended": recommended,
        "native_upgrade_supported": native_upgrade_supported,
    }


def get_app_version() -> str:
    try:
        return importlib.metadata.version("certify-reverse")
    except Exception:
        return "unknown"


def get_app_commit() -> str:
    return env_first("CERTIFY_REVERSE_COMMIT", "APP_COMMIT", default="unknown")


def caddy_has_plugin(provider: str) -> bool:
    if not CADDY.exists():
        return False
    mods = run([str(CADDY), "list-modules"]).splitlines()
    return any(provider in m for m in mods)


def build_caddy(dns_provider: str, caddy_version: str = "latest") -> None:
    log.info(
        "Building Caddy version %s with dns.providers.%s",
        hl(caddy_version),
        hl(dns_provider),
    )
    cache_root = WORK / ".cache"
    go_build_cache = cache_root / "go-build"
    go_mod_cache = cache_root / "go-mod"
    go_tmp = WORK / ".tmp"
    for d in (WORK, cache_root, go_build_cache, go_mod_cache, go_tmp):
        d.mkdir(parents=True, exist_ok=True)

    tmp_output = WORK / "caddy-rebuild.new"
    if tmp_output.exists():
        tmp_output.unlink()

    env = os.environ.copy()
    env["GOTOOLCHAIN"] = "auto"
    # Containers already grant NET_BIND_SERVICE at runtime; avoid xcaddy setcap
    # attempts that require CAP_SETFCAP during non-root rebuilds.
    env["XCADDY_SETCAP"] = "0"
    env["HOME"] = str(WORK)
    env["XDG_CACHE_HOME"] = str(cache_root)
    env["GOCACHE"] = str(go_build_cache)
    env["GOMODCACHE"] = str(go_mod_cache)
    env["TMPDIR"] = str(go_tmp)
    run(
        [
            "xcaddy",
            "build",
            caddy_version,
            "--with",
            f"github.com/caddy-dns/{dns_provider}",
            "--output",
            str(tmp_output),
        ],
        env=env,
        cwd=WORK,
    )
    if not tmp_output.exists():
        raise RuntimeError(f"xcaddy did not produce output binary: {tmp_output}")
    tmp_output.replace(CADDY)
    log.info("Installed rebuilt Caddy binary at %s", hl(CADDY))


def log_if_changed(path: Path, new_content: str, title: str) -> None:
    old_content = ""
    if path.exists():
        old_content = path.read_text(encoding="utf-8")

    if old_content == new_content:
        log.info("%s unchanged -> %s", title, hl(path))
        return

    if old_content:
        log.info("%s changed; logging unified diff before overwrite", title)
        diff = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"old/{path.name}",
            tofile=f"new/{path.name}",
            lineterm="",
        )
        for line in diff:
            log.info("DIFF %s", line)
    else:
        log.info("%s created -> %s", title, hl(path))

    path.write_text(new_content, encoding="utf-8")


def format_caddyfile_content(content: str) -> str:
    """Format Caddyfile text using `caddy fmt` when available."""
    if not CADDY.exists():
        return content
    try:
        p = subprocess.run(
            [str(CADDY), "fmt"],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception:
        return content

    if p.returncode == 0 and p.stdout.strip():
        return p.stdout
    return content


def format_caddyfile_in_place(path: Path) -> None:
    """Format a written Caddyfile on disk to silence runtime adapter warnings."""
    if not CADDY.exists() or not path.exists():
        return
    try:
        p = subprocess.run(
            [str(CADDY), "fmt", "--overwrite", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if p.returncode == 0:
            log.debug("Formatted Caddyfile in place: %s", hl(path))
    except Exception:
        pass


def prepare_caddy_runtime_env() -> None:
    """Set writable runtime dirs so non-root Caddy doesn't use '/.config' or '/.local'."""
    home = DATADIR
    xdg_config = DATADIR / ".config"
    xdg_data = DATADIR / ".local" / "share"
    xdg_cache = DATADIR / ".cache"
    for d in (home, xdg_config, xdg_data, xdg_cache):
        d.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home)
    os.environ["XDG_CONFIG_HOME"] = str(xdg_config)
    os.environ["XDG_DATA_HOME"] = str(xdg_data)
    os.environ["XDG_CACHE_HOME"] = str(xdg_cache)


def _parse_crtsh_time(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _crtsh_latest(entries: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    if not entries:
        return None, "none"
    latest: dict[str, Any] | None = None
    latest_dt: datetime | None = None
    for row in entries:
        not_after = _parse_crtsh_time(str(row.get("not_after", "")).strip())
        entry_ts = _parse_crtsh_time(str(row.get("entry_timestamp", "")).strip())
        candidate = not_after or entry_ts
        if candidate is None:
            continue
        if latest_dt is None or candidate > latest_dt:
            latest_dt = candidate
            latest = row
    if latest is None:
        return entries[0], "unknown"

    now = datetime.now(timezone.utc)
    nb = _parse_crtsh_time(str(latest.get("not_before", "")).strip())
    na = _parse_crtsh_time(str(latest.get("not_after", "")).strip())
    if nb and na:
        validity = "valid" if nb <= now <= na else "expired/not-yet-valid"
    elif na:
        validity = "valid" if now <= na else "expired"
    else:
        validity = "unknown"
    return latest, validity


def fetch_crtsh_state(domain: str) -> dict[str, Any]:
    url = f"https://crt.sh/?q={quote_plus(domain)}&output=json"
    req = Request(url, headers={"User-Agent": "certify-reverse"})
    with urlopen(req, timeout=15) as r:
        payload = r.read().decode("utf-8")
    entries = json.loads(payload) if payload.strip() else []
    if not isinstance(entries, list):
        entries = []

    latest, validity = _crtsh_latest(entries)
    state: dict[str, Any] = {
        "domain": domain,
        "source_url": url,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "match_count": len(entries),
        "latest": latest,
        "latest_validity": validity,
        "entries": entries,
    }

    latest_id = latest.get("id") if isinstance(latest, dict) else "n/a"
    latest_not_after = latest.get("not_after") if isinstance(latest, dict) else "n/a"
    log.info(
        "crt.sh domain=%s matches=%s latest_id=%s latest_not_after=%s validity=%s",
        hl(domain),
        hl(len(entries)),
        hl(latest_id),
        hl(latest_not_after),
        hl(validity),
    )
    return state


def write_status_json(path: Path, payload: dict[str, Any], title: str) -> None:
    new_content = json.dumps(payload, indent=2, sort_keys=True)
    old_content = path.read_text(encoding="utf-8") if path.exists() else ""
    if new_content == old_content:
        log.info("%s unchanged -> %s", title, hl(path))
        return
    path.write_text(new_content, encoding="utf-8")
    log.info("%s updated -> %s", title, hl(path))


def get_caddy_certificates() -> dict[str, Any]:
    if not CADDY.exists():
        raise RuntimeError("Caddy binary not found")

    config_json = run([str(CADDY), "config", "--adapter", "caddyfile", "--config", str(CFILE)])
    config_data = yaml.safe_load(config_json)

    certs_info: dict[str, Any] = {"certificates": [], "ca_certificates": [], "timestamp": time.time()}
    if "apps" in config_data and "tls" in config_data["apps"]:
        tls_app = config_data["apps"]["tls"]
        if "automation" in tls_app and "policies" in tls_app["automation"]:
            for policy in tls_app["automation"]["policies"]:
                subjects = policy.get("subjects")
                if isinstance(subjects, list):
                    certs_info["certificates"].extend(subjects)

    return certs_info


def print_certificates() -> None:
    certs = get_caddy_certificates()
    print("=== Caddy Internal Certificates ===")
    print(f"Retrieved at: {time.ctime(certs['timestamp'])}\n")

    if certs["certificates"]:
        print("Managed Certificates:")
        for i, cert in enumerate(certs["certificates"], 1):
            print(f"  {i}. {cert}")


def export_caddy_internal_certs() -> dict[str, str]:
    cert_info = auto_export_internal_ca()
    if not cert_info:
        raise RuntimeError(
            "Could not export internal CA certificate yet. Start Caddy once so PKI files are created."
        )
    log.info("Exported Caddy internal CA certs to %s", cert_info["export_dir"])
    return {
        "ca_cert_pem": cert_info["ca_cert_pem"],
        "ca_cert_crt": cert_info["ca_cert_crt"],
        "export_dir": cert_info["export_dir"],
    }


def auto_export_internal_ca() -> dict[str, str] | None:
    cert_export_dir = DATADIR / "exported-certs"
    cert_export_dir.mkdir(parents=True, exist_ok=True)

    pki_dirs = [
        DATADIR / "pki" / "ca" / "internal",
        DATADIR / "pki" / "authorities" / "internal",
        DATADIR / "caddy" / "pki" / "authorities" / "internal",
    ]

    for pki_dir in pki_dirs:
        if not pki_dir.exists():
            continue
        for filename in ["root.crt", "ca.crt", "root.pem", "ca.pem", "intermediate.crt", "intermediate.pem"]:
            ca_path = pki_dir / filename
            if ca_path.exists() and ca_path.stat().st_size > 0:
                ca_content = ca_path.read_text(encoding="utf-8")
                pem = cert_export_dir / "caddy-internal-ca.pem"
                crt = cert_export_dir / "caddy-internal-ca.crt"
                pem.write_text(ca_content, encoding="utf-8")
                crt.write_text(ca_content, encoding="utf-8")
                return {
                    "ca_cert_pem": str(pem),
                    "ca_cert_crt": str(crt),
                    "export_dir": str(cert_export_dir),
                    "source": "storage",
                }

    existing_pem = cert_export_dir / "caddy-internal-ca.pem"
    existing_crt = cert_export_dir / "caddy-internal-ca.crt"
    if existing_pem.exists() and existing_pem.stat().st_size > 100:
        return {
            "ca_cert_pem": str(existing_pem),
            "ca_cert_crt": str(existing_crt),
            "export_dir": str(cert_export_dir),
            "source": "existing",
        }

    return None


def copy_ca_to_service_directories(cfg: ReverseProxyConfig) -> None:
    main_ca_pem = DATADIR / "exported-certs" / "caddy-internal-ca.pem"
    main_ca_crt = DATADIR / "exported-certs" / "caddy-internal-ca.crt"

    if not main_ca_pem.exists() or not main_ca_crt.exists():
        log.warning("Main CA certificate not available yet; skipping service CA copies")
        return

    for upstream in cfg.upstreams:
        service_dir = DATADIR / upstream.subdomain
        service_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(main_ca_pem, service_dir / "caddy-internal-ca.pem")
        shutil.copy2(main_ca_crt, service_dir / "caddy-internal-ca.crt")

        readme_content = f"""# CA Certificate for {upstream.subdomain}

- Subdomain: {upstream.subdomain}.{cfg.domain}
- Target: {upstream.scheme}://{upstream.ip}:{upstream.port}
"""
        (service_dir / "README.md").write_text(readme_content, encoding="utf-8")


def auto_export_ca_certificates(cfg: ReverseProxyConfig) -> None:
    try:
        export_caddy_internal_certs()
    except Exception as e:
        log.warning("Automatic CA export failed (normal on first startup): %s", e)
    copy_ca_to_service_directories(cfg)


def generate_internal_service_certs(cfg: ReverseProxyConfig) -> None:
    service_certs_dir = DATADIR / "service-certs"
    service_certs_dir.mkdir(parents=True, exist_ok=True)

    for upstream in cfg.upstreams:
        if not upstream.is_https:
            continue
        service_name = f"{upstream.subdomain}.{cfg.domain}"
        cert_path = service_certs_dir / upstream.subdomain
        cert_path.mkdir(parents=True, exist_ok=True)
        try:
            run(
                [
                    str(CADDY),
                    "pki",
                    "certificate",
                    "--ca",
                    "internal",
                    "--host",
                    service_name,
                    "--host",
                    upstream.ip,
                    "--out-cert",
                    str(cert_path / "cert.pem"),
                    "--out-key",
                    str(cert_path / "key.pem"),
                ]
            )
            log.info("Generated internal service cert for %s", service_name)
        except Exception as e:
            log.warning("Failed to generate service certificate for %s: %s", service_name, e)


def run_extensions(cfg: ReverseProxyConfig) -> None:
    for u in cfg.upstreams:
        if not u.is_https or not u.trust_pool or not u.ext_name:
            continue
        try:
            mod = importlib.import_module(f"trust_ext.{u.ext_name}")
            ext_cls = getattr(mod, "TrustExtension")
            ext = ext_cls(**u.ext_params)
            if not ext.status(u):
                log.info("Issuing certificate for %s via %s", u.subdomain, u.ext_name)
                ext.issue(u)
            else:
                log.debug("Certificate for %s ok – expires %s", u.subdomain, ext.status(u))
        except Exception as e:
            log.error("Extension %s failed on %s: %s", u.ext_name, u.subdomain, e)


def write_status_assets(cfg: ReverseProxyConfig) -> None:
    write_static_assets()

    update_info = check_caddy_update_status()
    public_meta = {
        "certify_reverse_version": get_app_version(),
        "certify_reverse_commit": get_app_commit(),
        "domain": cfg.domain,
        "email": cfg.email,
        "dns_provider": cfg.dns_provider,
        "caddy_requested_version": cfg.caddy_version,
        "caddy_built_version": update_info.get("built", "unknown"),
        "caddy_latest_version": update_info.get("latest", "unknown"),
        "caddy_update_recommended": update_info.get("recommended"),
        "caddy_native_upgrade_supported": update_info.get("native_upgrade_supported"),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    rec = update_info.get("recommended")
    rec_text = "update recommended" if rec else "up-to-date/unknown"
    log.info(
        "Caddy versions: built=%s latest=%s recommendation=%s",
        hl(update_info.get("built", "unknown")),
        hl(update_info.get("latest", "unknown")),
        hl(rec_text),
    )
    acme_state = {
        "state": "unknown",
        "note": "Runtime ACME challenge status is not directly exposed to browser clients.",
        "subjects": [f"{u.subdomain}.{cfg.domain}" for u in cfg.upstreams],
        "generated_at": public_meta["generated_at"],
    }
    try:
        crtsh_state = fetch_crtsh_state(cfg.domain)
    except Exception as e:
        log.warning("crt.sh query failed for %s: %s", hl(cfg.domain), e)
        crtsh_state = {
            "domain": cfg.domain,
            "generated_at": public_meta["generated_at"],
            "error": str(e),
            "entries": [],
            "match_count": 0,
            "latest": None,
            "latest_validity": "unknown",
        }

    log_if_changed(INDEX_HTML, render_status_index_html(cfg, public_meta), "status index.html")
    write_status_json(ACME_STATE_JSON, acme_state, "acme-state.json")
    write_status_json(CRTSH_STATE_JSON, crtsh_state, "crtsh-state.json")


def write_static_assets() -> None:
    favicon_path = DATADIR / "favicon.ico"
    try:
        favicon_bytes = (
            importlib.resources.files("certify_reverse")
            .joinpath("static", "favicon.ico")
            .read_bytes()
        )
    except Exception as e:
        log.warning("Static favicon asset unavailable: %s", e)
        return

    old_bytes = favicon_path.read_bytes() if favicon_path.exists() else b""
    if old_bytes == favicon_bytes:
        log.info("favicon.ico unchanged -> %s", hl(favicon_path))
        return

    favicon_path.write_bytes(favicon_bytes)
    log.info("favicon.ico updated -> %s", hl(favicon_path))


def print_update_status() -> None:
    status = check_caddy_update_status()
    print("=== Caddy Update Check ===")
    print(f"Built Version:  {hl(status.get('built'))}")
    print(f"Latest Version: {hl(status.get('latest'))}")
    print(
        "Native upgrade command:",
        hl("supported" if status.get("native_upgrade_supported") else "not available"),
    )
    if status.get("recommended") is True:
        print(f"Recommendation: {hl('update recommended')}")
    elif status.get("recommended") is False:
        print(f"Recommendation: {hl('up-to-date')}")
    else:
        print(f"Recommendation: unknown ({status.get('error', 'n/a')})")


def main(rebuild: bool = False, show_certs: bool = False, print_caddyfile: bool = False) -> None:
    if show_certs:
        print_certificates()
        return

    set_datadir(DATADIR)
    cfg = ReverseProxyConfig.from_sources()
    log.info(
        "Loaded env+upstreams config for domain %s with %s upstream(s), dnsmasq mode %s target %s",
        hl(cfg.domain),
        hl(len(cfg.upstreams)),
        hl(cfg.dnsmasq_address_mode),
        hl(cfg.dnsmasq_address_ip),
    )

    caddyfile_content = format_caddyfile_content(render_caddy(cfg))

    if print_caddyfile:
        print(caddyfile_content)
        return

    if rebuild or not CADDY.exists() or not caddy_has_plugin(cfg.dns_provider):
        build_caddy(cfg.dns_provider, cfg.caddy_version)
    else:
        log.info(
            "Existing Caddy binary already has dns provider %s; skipping rebuild",
            hl(cfg.dns_provider),
        )

    run_extensions(cfg)

    log_if_changed(CFILE, caddyfile_content, "Caddyfile")
    format_caddyfile_in_place(CFILE)
    log_if_changed(DNSMASQ, render_dnsmasq(cfg), "dnsmasq.conf")

    # caddy trust needs a running admin endpoint; skip pre-run invocation.
    log.info("Skipping 'caddy trust' during bootstrap (admin endpoint not yet running)")

    try:
        cert_info = auto_export_internal_ca()
        if cert_info:
            instructions_content = render_upstream_tls_setup_guide(cert_info)
            log_if_changed(DATADIR / "upstream-tls-setup.md", instructions_content, "upstream-tls-setup.md")
    except Exception as e:
        log.warning("Failed to auto-export CA certificate: %s", e)

    auto_export_ca_certificates(cfg)
    generate_internal_service_certs(cfg)
    write_status_assets(cfg)

    caddy_runtime_file = CFILE
    if CFILE_OVERWRITE.exists():
        log.warning(
            "Detected %s; using overwrite file instead of generated Caddyfile",
            hl(CFILE_OVERWRITE),
        )
        caddy_runtime_file = CFILE_OVERWRITE

    prepare_caddy_runtime_env()
    log.info("Starting Caddy using config %s", hl(caddy_runtime_file))
    os.execvp(str(CADDY), [str(CADDY), "run", "--config", str(caddy_runtime_file), "--adapter", "caddyfile"])


def entrypoint() -> None:
    configure_logging()
    try:
        WORK.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log.error("Cannot write runtime work directory: %s", WORK)
        log.error("Ensure /data is writable and mounted correctly.")
        sys.exit(1)

    arg = argparse.ArgumentParser(
        description="Caddy DNS-01 bootstrapper with certificate management",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    arg.add_argument("--force-build", action="store_true", help="Deprecated alias for --rebuild-caddy")
    arg.add_argument("--rebuild-caddy", action="store_true", help="Force rebuild Caddy binary")
    arg.add_argument("--update-caddy", action="store_true", help="Force rebuild Caddy binary")
    arg.add_argument("--show-certs", action="store_true", help="Show internal certificates and exit")
    arg.add_argument("--export-certs", action="store_true", help="Export internal CA certificate and exit")
    arg.add_argument("--create-service-dirs", action="store_true", help="Create service CA dirs and exit")
    arg.add_argument("--check-updates", action="store_true", help="Compare built Caddy version with latest release")
    arg.add_argument("--print-caddyfile", action="store_true", help="Print generated Caddyfile and exit")

    opts = arg.parse_args()

    if opts.check_updates:
        print_update_status()
        sys.exit(0)

    if opts.export_certs:
        try:
            cert_info = export_caddy_internal_certs()
            instructions = render_upstream_tls_setup_guide(cert_info)
            (DATADIR / "upstream-tls-setup.md").write_text(instructions, encoding="utf-8")
            print("✅ Exported Caddy internal certificates")
            print(f"   CA Certificate (PEM): {cert_info['ca_cert_pem']}")
            print(f"   CA Certificate (CRT): {cert_info['ca_cert_crt']}")
            print(f"   Export Directory: {cert_info['export_dir']}")
        except Exception as e:
            print(f"❌ Failed to export certificates: {e}")
            sys.exit(1)
        sys.exit(0)

    if opts.create_service_dirs:
        try:
            cfg = ReverseProxyConfig.from_sources()
            auto_export_ca_certificates(cfg)
            print("✅ Created service-specific CA certificate directories")
        except Exception as e:
            print(f"❌ Failed to create service directories: {e}")
            sys.exit(1)
        sys.exit(0)

    rebuild = bool(opts.force_build or opts.rebuild_caddy or opts.update_caddy)
    try:
        main(
            rebuild=rebuild,
            show_certs=opts.show_certs,
            print_caddyfile=opts.print_caddyfile,
        )
    except InvalidSetupError as e:
        log.error("Configuration is invalid: %s", e)
        log.error("Startup halted. Fix config and restart the container.")
        log.error("Expected files: /config/.env and /config/upstreams.yml")
        log.error(
            "Quick start: cp .env.example .env && cp upstreams.yml.example upstreams.yml"
        )
        # Exit cleanly to avoid restart loops for static setup errors.
        sys.exit(0)


if __name__ == "__main__":
    entrypoint()
