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
import ipaddress
import json
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from http.client import HTTPException
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
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PROVIDER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_CADDY_VERSION_RE = re.compile(
    r"^(?:latest|v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)
_DNS_TOKEN_FIELD_DEFAULTS = {
    "desec": "token",
}
_RESERVED_UPSTREAM_SUBDOMAINS = {"status", "internal-ca"}
_GITHUB_MAX_RESPONSE_BYTES = 1024 * 1024
_CRTSH_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_CRTSH_MAX_ENTRIES = 5000
_HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?$")
_DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+$")
_STATUS_LOOKUP_ERRORS = (
    URLError,
    TimeoutError,
    OSError,
    HTTPException,
    ValueError,
    UnicodeDecodeError,
)


class StripAnsiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        s = super().format(record)
        return _ANSI_RE.sub("", s)


class InvalidSetupError(Exception):
    """Raised when required configuration is missing or malformed."""


def hl(value: Any) -> str:
    return f"{_C_HL}{value}{_C_RESET}"


def _fsync_directory(path: Path) -> None:
    """Best-effort directory sync after an atomic replacement."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write_text(path: Path, content: str, *, mode: int | None = None) -> None:
    """Replace a text file atomically using a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            tmp_path.chmod(mode)
        elif path.exists():
            tmp_path.chmod(path.stat().st_mode & 0o777)
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        tmp_path.unlink(missing_ok=True)


def _atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    """Replace a binary file atomically using a temporary file in the same directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            tmp_path.chmod(mode)
        elif path.exists():
            tmp_path.chmod(path.stat().st_mode & 0o777)
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        tmp_path.unlink(missing_ok=True)


def _atomic_copy_file(source: Path, destination: Path, *, mode: int | None = None) -> None:
    _atomic_write_bytes(destination, source.read_bytes(), mode=mode)


def _read_limited_response(response: Any, max_bytes: int, label: str) -> bytes:
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"{label} response exceeds {max_bytes} bytes")
    return payload


def _validated_dns_name(value: str, label: str, *, allow_underscore: bool = False) -> str:
    if not isinstance(value, str):
        raise InvalidSetupError(f"{label} must be a string")
    normalized = value.strip().rstrip(".").lower()
    if not normalized or len(normalized) > 253:
        raise InvalidSetupError(f"{label} must be a non-empty DNS name no longer than 253 characters")
    matcher = _HOST_LABEL_RE if allow_underscore else _DNS_LABEL_RE
    if any(not matcher.fullmatch(part) for part in normalized.split(".")):
        raise InvalidSetupError(f"{label} contains an invalid DNS label: {value!r}")
    return normalized


def _validated_upstream_host(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidSetupError("upstream ip/host must be a string")
    normalized = value.strip()
    if not normalized or any(ch.isspace() or ord(ch) < 32 for ch in normalized):
        raise InvalidSetupError(f"upstream ip/host is invalid: {value!r}")
    try:
        ipaddress.ip_address(normalized)
        return normalized
    except ValueError:
        return _validated_dns_name(normalized, "upstream ip/host", allow_underscore=True)


def default_dns_token_field(provider: str) -> str:
    """Return the known Caddyfile credential directive for a DNS provider."""
    return _DNS_TOKEN_FIELD_DEFAULTS.get(provider.lower(), "api_token")


def configure_logging() -> None:
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return

    file_logging_ready = False
    try:
        DATADIR.mkdir(parents=True, exist_ok=True)
        LOGDIR.mkdir(parents=True, exist_ok=True)
        rot = RotatingFileHandler(LOGDIR / "app.log", maxBytes=100_000, backupCount=5)
        rot.setFormatter(StripAnsiFormatter(LOGFMT))
        log.addHandler(rot)
        file_logging_ready = True
    except OSError:
        file_logging_ready = False

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter(LOGFMT))
    log.addHandler(console)

    _LOG_CONFIGURED = True
    if file_logging_ready:
        log.info("Logging initialized - output to stderr and %s", LOGDIR / "app.log")
    else:
        log.warning("Logging initialized in stderr-only mode (cannot write %s)", LOGDIR)


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

    def __post_init__(self) -> None:
        self.subdomain = _validated_dns_name(self.subdomain, "upstream subdomain")
        self.ip = _validated_upstream_host(self.ip)
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise InvalidSetupError(f"upstream '{self.subdomain}' port must be an integer from 1 to 65535")
        if not isinstance(self.scheme, str) or self.scheme.lower().strip() not in {"http", "https"}:
            raise InvalidSetupError(f"upstream '{self.subdomain}' scheme must be 'http' or 'https'")
        self.scheme = self.scheme.lower().strip()
        if not isinstance(self.skip_verify, bool):
            raise InvalidSetupError(f"upstream '{self.subdomain}' skip_verify must be a boolean")
        if not isinstance(self.forward_auth_headers, bool):
            raise InvalidSetupError(
                f"upstream '{self.subdomain}' forward_auth_headers must be a boolean"
            )
        if self.trust_pool is not None:
            if not isinstance(self.trust_pool, str) or not self.trust_pool.strip():
                raise InvalidSetupError(f"upstream '{self.subdomain}' trust_pool must be a path string")
            trust_pool = Path(self.trust_pool).expanduser()
            if not trust_pool.is_absolute():
                raise InvalidSetupError(f"upstream '{self.subdomain}' trust_pool must be an absolute path")
            self.trust_pool = str(trust_pool)
        if self.ext_name is not None:
            if not isinstance(self.ext_name, str) or not _IDENTIFIER_RE.fullmatch(self.ext_name):
                raise InvalidSetupError(
                    f"upstream '{self.subdomain}' ext_name must be a Python identifier"
                )
        if not isinstance(self.ext_params, dict):
            raise InvalidSetupError(f"upstream '{self.subdomain}' ext_params must be a mapping")

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
    dns_token_field: str = ""
    dnsmasq_address_mode: str = "manual"
    dnsmasq_address_ip: str = "10.0.0.1"
    upstreams: list[Upstream] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.dns_provider, str) or not _PROVIDER_RE.fullmatch(self.dns_provider):
            raise InvalidSetupError(
                "DNS_PROVIDER must contain only letters, numbers, underscores, and hyphens"
            )
        self.dns_provider = self.dns_provider.lower()
        if not isinstance(self.dns_token, str) or not self.dns_token.strip():
            raise InvalidSetupError("DNS_TOKEN must not be empty")
        self.dns_token = self.dns_token.strip()
        if not isinstance(self.dns_token_field, str):
            raise InvalidSetupError("CADDY_DNS_PLUGIN_TOKEN_FIELD must be a Caddy identifier")
        self.dns_token_field = self.dns_token_field.strip()
        if not self.dns_token_field:
            self.dns_token_field = default_dns_token_field(self.dns_provider)
        if not _IDENTIFIER_RE.fullmatch(self.dns_token_field):
            raise InvalidSetupError("CADDY_DNS_PLUGIN_TOKEN_FIELD must be a Caddy identifier")
        if not isinstance(self.email, str) or not _EMAIL_RE.fullmatch(self.email.strip()):
            raise InvalidSetupError("ACME_EMAIL must be a valid email address")
        self.email = self.email.strip()
        self.domain = _validated_dns_name(self.domain, "DOMAIN")
        if not isinstance(self.caddy_version, str):
            raise InvalidSetupError("CADDY_VERSION must be a version string")
        self.caddy_version = self.caddy_version.strip()
        if not _CADDY_VERSION_RE.fullmatch(self.caddy_version):
            raise InvalidSetupError(
                "CADDY_VERSION must be 'latest' or a semantic version such as v2.10.0"
            )
        if self.caddy_version != "latest" and not self.caddy_version.startswith("v"):
            self.caddy_version = f"v{self.caddy_version}"
        if not isinstance(self.dnsmasq_address_mode, str):
            raise InvalidSetupError("DNSMASQ_ADDRESS_MODE must be one of: manual, host-src-ip, auto")
        self.dnsmasq_address_mode = self.dnsmasq_address_mode.strip().lower()
        if self.dnsmasq_address_mode not in {"manual", "host-src-ip", "auto"}:
            raise InvalidSetupError("DNSMASQ_ADDRESS_MODE must be one of: manual, host-src-ip, auto")
        if not is_ipv4(self.dnsmasq_address_ip):
            raise InvalidSetupError("DNSMASQ_ADDRESS_IP must resolve to a valid IPv4 address")
        seen_subdomains: set[str] = set()
        for upstream in self.upstreams:
            if upstream.subdomain in _RESERVED_UPSTREAM_SUBDOMAINS:
                raise InvalidSetupError(
                    f"Upstream subdomain '{upstream.subdomain}' is reserved for a generated endpoint"
                )
            if upstream.subdomain in seen_subdomains:
                raise InvalidSetupError(
                    f"Upstream subdomain '{upstream.subdomain}' is configured more than once"
                )
            seen_subdomains.add(upstream.subdomain)

    @classmethod
    def from_sources(cls) -> "ReverseProxyConfig":
        load_env_file(ENV_FILE)

        dns_provider = must_env("DNS_PROVIDER")
        dns_token = must_env("DNS_TOKEN")
        email = os.getenv("ACME_EMAIL", "admin@example.com")
        domain = must_env("DOMAIN")
        caddy_version = os.getenv("CADDY_VERSION", "latest").strip() or "latest"
        dns_token_field = env_first(
            "CADDY_DNS_PLUGIN_TOKEN_FIELD",
            default="",
        )
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
            dns_token_field=dns_token_field,
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
    try:
        socket.inet_aton(value)
    except OSError:
        return False
    return value.count(".") == 3


def resolve_hostname_ipv4(name: str) -> str | None:
    try:
        return socket.gethostbyname(name)
    except OSError:
        return None


def _extract_src_ip_from_route(route_output: str) -> str | None:
    m = re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)\b", route_output)
    return m.group(1) if m else None


def derive_dnsmasq_address_ip(mode: str, manual_ip: str) -> str:
    mode = mode.strip().lower()
    if mode not in {"manual", "host-src-ip", "auto"}:
        raise InvalidSetupError(
            "DNSMASQ_ADDRESS_MODE must be one of: manual, host-src-ip, auto"
        )
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

    if not is_ipv4(manual_ip):
        raise InvalidSetupError(
            "DNSMASQ_ADDRESS_IP must be a valid IPv4 address or resolve to one"
        )
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
    except (subprocess.SubprocessError, OSError, ValueError) as e:
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

    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if not _ENV_KEY_RE.fullmatch(k):
            raise InvalidSetupError(f"Invalid environment key in {path}:{line_number}: {k!r}")
        v = v.strip().strip('"').strip("'")
        # File-based runtime config is authoritative for this app and must
        # override inherited image/base environment defaults.
        os.environ[k] = v


def load_upstreams(path: Path) -> list[Upstream]:
    if not path.exists():
        raise InvalidSetupError(
            f"Missing upstreams file: {path}. Copy upstreams.yml.example to upstreams.yml."
        )

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise InvalidSetupError(f"Could not parse {path}: {e}") from e
    if not isinstance(data, dict):
        raise InvalidSetupError("upstreams.yml must contain a top-level mapping")

    upstreams: list[Upstream] = []
    normalized_subdomains: dict[str, str] = {}
    for subdomain, spec in data.items():
        if not isinstance(subdomain, str):
            raise InvalidSetupError("Every upstream key must be a string subdomain")
        if not isinstance(spec, dict):
            raise InvalidSetupError(f"Upstream '{subdomain}' must be an object")
        try:
            upstream = Upstream(subdomain=subdomain, **spec)
        except TypeError as e:
            raise InvalidSetupError(f"Invalid fields for upstream '{subdomain}': {e}") from e
        previous = normalized_subdomains.get(upstream.subdomain)
        if previous is not None:
            raise InvalidSetupError(
                f"Upstream subdomains {previous!r} and {subdomain!r} normalize to the same name"
            )
        normalized_subdomains[upstream.subdomain] = subdomain
        upstreams.append(upstream)

    return upstreams


def semver_tuple(version: str) -> tuple[int, int, int] | None:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def get_caddy_version(binary: Path) -> str:
    if not binary.exists():
        return "not-built"
    try:
        return run([str(binary), "version"]).strip()
    except (RuntimeError, OSError):
        return "unknown"


def get_built_caddy_version() -> str:
    return get_caddy_version(CADDY)


def get_latest_caddy_version() -> str:
    req = Request(
        "https://api.github.com/repos/caddyserver/caddy/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "certify-reverse"},
    )
    with urlopen(req, timeout=10) as r:
        payload = json.loads(
            _read_limited_response(r, _GITHUB_MAX_RESPONSE_BYTES, "GitHub release").decode(
                "utf-8"
            )
        )
    if not isinstance(payload, dict):
        raise ValueError("GitHub release response is not an object")
    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not _CADDY_VERSION_RE.fullmatch(tag_name):
        raise ValueError("GitHub release response does not contain a valid Caddy version")
    return tag_name


def check_caddy_update_status() -> dict[str, Any]:
    built = get_built_caddy_version()
    native_upgrade_supported = False
    if CADDY.exists():
        try:
            run([str(CADDY), "upgrade", "--help"])
            native_upgrade_supported = True
        except RuntimeError:
            native_upgrade_supported = False
    try:
        latest = get_latest_caddy_version()
    except _STATUS_LOOKUP_ERRORS as e:
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
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def get_app_commit() -> str:
    return env_first("CERTIFY_REVERSE_COMMIT", "APP_COMMIT", default="unknown")


def caddy_binary_has_plugin(binary: Path, provider: str) -> bool:
    if not binary.exists():
        return False
    try:
        mods = run([str(binary), "list-modules"]).splitlines()
    except (RuntimeError, OSError):
        return False
    expected = f"dns.providers.{provider}"
    return any(module.strip() == expected for module in mods)


def caddy_has_plugin(provider: str) -> bool:
    return caddy_binary_has_plugin(CADDY, provider)


def caddy_binary_matches_requested_version(binary: Path, requested_version: str) -> bool:
    """Return whether the installed Caddy satisfies an explicit requested version."""
    built_version = get_caddy_version(binary)
    if built_version in {"not-built", "unknown"}:
        return False
    if requested_version == "latest":
        return semver_tuple(built_version) is not None
    requested = requested_version.removeprefix("v")
    match = re.search(
        r"\bv?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)\b",
        built_version,
    )
    if match is None:
        return False
    built = match.group(1)
    if "-" in requested or "+" in requested:
        return built == requested
    return semver_tuple(built) == semver_tuple(requested)


def caddy_matches_requested_version(requested_version: str) -> bool:
    return caddy_binary_matches_requested_version(CADDY, requested_version)


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
    try:
        if not tmp_output.exists() or tmp_output.stat().st_size == 0:
            raise RuntimeError(f"xcaddy did not produce a non-empty output binary: {tmp_output}")
        if not os.access(tmp_output, os.X_OK):
            raise RuntimeError(f"xcaddy output is not executable: {tmp_output}")
        if not caddy_binary_has_plugin(tmp_output, dns_provider):
            raise RuntimeError(
                f"rebuilt Caddy is missing required module dns.providers.{dns_provider}"
            )
        if not caddy_binary_matches_requested_version(tmp_output, caddy_version):
            raise RuntimeError(
                f"rebuilt Caddy version {get_caddy_version(tmp_output)!r} does not match {caddy_version!r}"
            )
        with tmp_output.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(tmp_output, CADDY)
        _fsync_directory(CADDY.parent)
    finally:
        tmp_output.unlink(missing_ok=True)
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

    _atomic_write_text(path, new_content)


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
    except OSError:
        return content

    if p.returncode == 0 and p.stdout.strip():
        return p.stdout
    return content


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
        payload = _read_limited_response(r, _CRTSH_MAX_RESPONSE_BYTES, "crt.sh").decode(
            "utf-8"
        )
    raw_entries = json.loads(payload) if payload.strip() else []
    if not isinstance(raw_entries, list):
        raw_entries = []
    entries = [row for row in raw_entries if isinstance(row, dict)]
    ignored_entries = len(raw_entries) - len(entries)

    latest, validity = _crtsh_latest(entries)
    stored_entries = entries[:_CRTSH_MAX_ENTRIES]
    state: dict[str, Any] = {
        "domain": domain,
        "source_url": url,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "match_count": len(entries),
        "stored_count": len(stored_entries),
        "entries_truncated": len(entries) > len(stored_entries),
        "ignored_malformed_entries": ignored_entries,
        "latest": latest,
        "latest_validity": validity,
        "entries": stored_entries,
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
    _atomic_write_text(path, new_content)
    log.info("%s updated -> %s", title, hl(path))


def get_caddy_certificates() -> dict[str, Any]:
    if not CADDY.exists():
        raise RuntimeError("Caddy binary not found")

    config_json = run([str(CADDY), "config", "--adapter", "caddyfile", "--config", str(CFILE)])
    try:
        config_data = yaml.safe_load(config_json)
    except yaml.YAMLError as e:
        raise RuntimeError("Caddy returned invalid config JSON") from e
    if not isinstance(config_data, dict):
        raise RuntimeError("Caddy returned an empty or invalid config document")

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
        for filename in ["root.crt", "ca.crt", "root.pem", "ca.pem"]:
            ca_path = pki_dir / filename
            if ca_path.exists() and ca_path.stat().st_size > 0:
                ca_content = ca_path.read_text(encoding="utf-8")
                pem = cert_export_dir / "caddy-internal-ca.pem"
                crt = cert_export_dir / "caddy-internal-ca.crt"
                _atomic_write_text(pem, ca_content, mode=0o644)
                _atomic_write_text(crt, ca_content, mode=0o644)
                return {
                    "ca_cert_pem": str(pem),
                    "ca_cert_crt": str(crt),
                    "export_dir": str(cert_export_dir),
                    "source": "storage",
                }

    existing_pem = cert_export_dir / "caddy-internal-ca.pem"
    existing_crt = cert_export_dir / "caddy-internal-ca.crt"
    if existing_pem.exists() and existing_pem.stat().st_size > 100:
        if not existing_crt.exists() or existing_crt.stat().st_size <= 100:
            _atomic_copy_file(existing_pem, existing_crt, mode=0o644)
        return {
            "ca_cert_pem": str(existing_pem),
            "ca_cert_crt": str(existing_crt),
            "export_dir": str(cert_export_dir),
            "source": "existing",
        }
    if existing_crt.exists() and existing_crt.stat().st_size > 100:
        _atomic_copy_file(existing_crt, existing_pem, mode=0o644)
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

        _atomic_copy_file(main_ca_pem, service_dir / "caddy-internal-ca.pem", mode=0o644)
        _atomic_copy_file(main_ca_crt, service_dir / "caddy-internal-ca.crt", mode=0o644)

        readme_content = f"""# CA Certificate for {upstream.subdomain}

- Subdomain: {upstream.subdomain}.{cfg.domain}
- Target: {upstream.scheme}://{upstream.ip}:{upstream.port}
"""
        _atomic_write_text(service_dir / "README.md", readme_content, mode=0o644)


def auto_export_ca_certificates(cfg: ReverseProxyConfig) -> None:
    try:
        export_caddy_internal_certs()
    except RuntimeError as e:
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
        cert_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        cert_path.chmod(0o700)
        cert_tmp = cert_path / f".cert.pem.{os.getpid()}.tmp"
        key_tmp = cert_path / f".key.pem.{os.getpid()}.tmp"
        cert_final = cert_path / "cert.pem"
        key_final = cert_path / "key.pem"
        cert_tmp.unlink(missing_ok=True)
        key_tmp.unlink(missing_ok=True)
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
                    str(cert_tmp),
                    "--out-key",
                    str(key_tmp),
                ]
            )
            if not cert_tmp.exists() or cert_tmp.stat().st_size == 0:
                raise RuntimeError("Caddy did not produce a non-empty service certificate")
            if not key_tmp.exists() or key_tmp.stat().st_size == 0:
                raise RuntimeError("Caddy did not produce a non-empty service private key")
            cert_tmp.chmod(0o644)
            key_tmp.chmod(0o600)
            os.replace(cert_tmp, cert_final)
            os.replace(key_tmp, key_final)
            _fsync_directory(cert_path)
            log.info("Generated internal service cert for %s", service_name)
        except (RuntimeError, OSError) as e:
            log.warning("Failed to generate service certificate for %s: %s", service_name, e)
        finally:
            cert_tmp.unlink(missing_ok=True)
            key_tmp.unlink(missing_ok=True)


def run_extensions(cfg: ReverseProxyConfig) -> None:
    for u in cfg.upstreams:
        if not u.is_https or not u.trust_pool or not u.ext_name:
            continue
        try:
            mod = importlib.import_module(f"trust_ext.{u.ext_name}")
            ext_cls = getattr(mod, "TrustExtension")
            ext = ext_cls(**u.ext_params)
            status = ext.status(u)
            if not status:
                log.info("Issuing certificate for %s via %s", u.subdomain, u.ext_name)
                ext.issue(u)
            else:
                log.debug("Certificate for %s ok – expires %s", u.subdomain, status)
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
    except _STATUS_LOOKUP_ERRORS as e:
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
    except (FileNotFoundError, ModuleNotFoundError, OSError) as e:
        log.warning("Static favicon asset unavailable: %s", e)
        return

    old_bytes = favicon_path.read_bytes() if favicon_path.exists() else b""
    if old_bytes == favicon_bytes:
        log.info("favicon.ico unchanged -> %s", hl(favicon_path))
        return

    _atomic_write_bytes(favicon_path, favicon_bytes, mode=0o644)
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
    os.environ["CADDY_DNS_PLUGIN"] = cfg.dns_provider
    os.environ["CADDY_DNS_PLUGIN_TOKEN"] = cfg.dns_token
    os.environ["CADDY_DNS_PLUGIN_TOKEN_FIELD"] = cfg.dns_token_field
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

    caddy_exists = CADDY.exists()
    plugin_matches = caddy_exists and caddy_has_plugin(cfg.dns_provider)
    version_matches = caddy_exists and caddy_matches_requested_version(cfg.caddy_version)
    if rebuild or not caddy_exists or not plugin_matches or not version_matches:
        if caddy_exists and not version_matches:
            log.info(
                "Existing Caddy version %s does not match requested %s; rebuilding",
                hl(get_built_caddy_version()),
                hl(cfg.caddy_version),
            )
        build_caddy(cfg.dns_provider, cfg.caddy_version)
    else:
        log.info(
            "Existing Caddy binary already has dns provider %s; skipping rebuild",
            hl(cfg.dns_provider),
        )

    # Reformat after a first-time rebuild so the generated file is atomically
    # installed in its final form instead of being rewritten in place later.
    caddyfile_content = format_caddyfile_content(render_caddy(cfg))
    run_extensions(cfg)

    log_if_changed(CFILE, caddyfile_content, "Caddyfile")
    log_if_changed(DNSMASQ, render_dnsmasq(cfg), "dnsmasq.conf")

    # caddy trust needs a running admin endpoint; skip pre-run invocation.
    log.info("Skipping 'caddy trust' during bootstrap (admin endpoint not yet running)")

    try:
        cert_info = auto_export_internal_ca()
        if cert_info:
            instructions_content = render_upstream_tls_setup_guide(cert_info)
            log_if_changed(DATADIR / "upstream-tls-setup.md", instructions_content, "upstream-tls-setup.md")
    except RuntimeError as e:
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
    arg.add_argument(
        "--rebuild-caddy-only",
        action="store_true",
        help="Rebuild and validate Caddy, then exit without starting the server",
    )
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

    if opts.rebuild_caddy_only:
        try:
            cfg = ReverseProxyConfig.from_sources()
            build_caddy(cfg.dns_provider, cfg.caddy_version)
            print(f"✅ Rebuilt Caddy: {get_built_caddy_version()}")
        except (InvalidSetupError, RuntimeError, OSError) as e:
            print(f"❌ Failed to rebuild Caddy: {e}")
            sys.exit(1)
        sys.exit(0)

    if opts.export_certs:
        try:
            cert_info = export_caddy_internal_certs()
            instructions = render_upstream_tls_setup_guide(cert_info)
            _atomic_write_text(
                DATADIR / "upstream-tls-setup.md",
                instructions,
                mode=0o644,
            )
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
        sys.exit(1)


if __name__ == "__main__":
    entrypoint()
