#!/usr/bin/env python3
"""
Runtime bootstrapper for Caddy with custom DNS-01 plug-in.

It performs, in order:
1. Read config.yml
2. Compile Caddy with dns.providers.<dns_provider>
3. Render Caddyfile from Jinja2 template
4. Exec the freshly-built Caddy
"""
import subprocess, sys, os, yaml, shutil, textwrap, logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from pathlib import Path
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler("/data/app.log", maxBytes=100000, backupCount=5),
        logging.StreamHandler(),
    ],
)

log = logging.getLogger(__name__)


BASE = Path("/")
CFG = BASE / "config.yml"
OUT = Path("/tmp/Caddyfile")  # rendered Caddyfile
BIN = Path("/tmp/caddy-rebuild")  # final binary location
WORK = Path("/tmp/caddybuild")  # build dir


@dataclass
class ReverseProxyConfig:
    """Configuration for reverse proxy."""

    dns_provider: str
    dns_token: str
    email: str
    upstreams: list[dict[str, str]]
    domain: str  # Default domain

    def __init__(
        self,
        dns_provider: str,
        dns_token: str,
        email: str,
        upstreams: list[dict[str, str]],
        domain: str,
    ):
        self.dns_provider = dns_provider
        self.dns_token = dns_token
        self.email = email
        self.upstreams = upstreams
        self.domain = domain

    def __str__(self):
        return f"ReverseProxyConfig(dns_provider={self.dns_provider}, dns_token={self.dns_token}, email={self.email}, upstreams={self.upstreams})"

    @classmethod
    def from_yaml(cls, yaml_str: str):
        """Create ReverseProxyConfig from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls(
            dns_provider=data["dns_provider"],
            dns_token=data["dns_token"],
            email=data["email"],
            upstreams=data["upstreams"],
            domain=data["domain"],
        )

    @classmethod
    def from_file(cls, file_path: str):
        """Create ReverseProxyConfig from a file."""
        with open(file_path, "r") as file:
            yaml_str = file.read()
        return cls.from_yaml(yaml_str)

    def render(self):
        return "\n".join(
            [
                f"reverse_proxy {upstream['host']} {upstream['port']}"
                for upstream in self.upstreams
            ]
        )

    def changed(self, other):
        """Check if the configuration has changed."""
        return (
            self.dns_provider != other.dns_provider
            or self.dns_token != other.dns_token
            or self.email != other.email
            or self.upstreams != other.upstreams
        )


class CaddyError(Exception):
    """Custom exception for Caddy errors."""

    pass


def run(cmd: list[str], **kw):
    """Run a command, stream output, bail on error."""
    print(f"+ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kw)


def check_output(cmd: list[str], **kw) -> str:
    """Run a command, stream output, bail on error."""
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, capture_output=True, **kw)
    return result.stdout.decode("utf-8")


def get_caddy_version():
    """Get the version of the Caddy binary."""
    try:
        output = check_output([str(BIN), "version"])
        return output.split()[1]
    except subprocess.CalledProcessError as e:
        print(f"Error getting Caddy version: {e}")
        sys.exit(1)


def get_caddy_build_info():
    """Get the build information of the Caddy binary."""
    try:
        output = check_output([str(BIN), "version", "--json"])
        return yaml.safe_load(output)
    except subprocess.CalledProcessError as e:
        print(f"Error getting Caddy build info: {e}")
        sys.exit(1)


def get_caddy_config():
    """Get the current Caddy configuration."""
    try:
        output = check_output([str(BIN), "config", "show"])
        return yaml.safe_load(output)
    except subprocess.CalledProcessError as e:
        print(f"Error getting Caddy config: {e}")
        sys.exit(1)


def get_caddy_dns_plugins():
    """Get the DNS plugins build in the current
    caddy bin."""
    try:
        output = check_output([str(BIN), "list-modules"]).strip()
        print(f"Output of list-modules: {output}")
        log.debug(f"Output of list-modules: {output}")
        o = [x for x in output.splitlines() if x.strip().startswith("dns.provider")]
        print(f"Output of DNS plugins: {o}")

        return o
    except subprocess.CalledProcessError as e:
        print(f"Error getting Caddy DNS plugins: {e}")
        sys.exit(1)


def has_dns_plugin(dns_provider):
    """Check if the DNS provider is already in the current Caddy build."""
    try:
        o = get_caddy_dns_plugins()
        return any(dns_provider in x for x in o)
    except subprocess.CalledProcessError as e:
        print(f"Error checking DNS plugin: {e}")
        sys.exit(1)


def build_caddy():
    global CONFIG
    log.info(f"Building Caddy with dns.providers.{CONFIG.dns_provider} …")
    if os.path.exists(BIN):
        log.info(f"Removing existing Caddy binary at {BIN} …")
        os.remove(BIN)
    run(
        [
            "xcaddy",
            "build",
            f"--with",
            f"github.com/caddy-dns/{CONFIG.dns_provider}",
            "--output",
            str(BIN),
            "--with",
            "github.com/caddyserver/caddy/v2/cmd",
        ],
        cwd=WORK,
    )


# ---------- global options ----------
# {
#   email {{ cfg.email | default("admin@example.com") }}
#   acme_dns {{ dns_provider }} {
#       token {{ dns_token | quote }}
#   }
# }

# # ---------- reverse-proxy targets ----------
# {% for t in targets %}
# {{ t.subdomain }} {
#   reverse_proxy {{ t.ip }}:{{ t.port }}
# }
# {% endfor %}


def _render_global_options(dns_provider, dns_token, email):
    return textwrap.dedent(
        f"""
        # ---------- global options ----------
        # global options
        {{
            email {email}
            acme_dns {dns_provider} {{
                token {dns_token}
                # propagation_timeout  120   # seconds to wait until TXT seen
                # polling_interval     4    # seconds between checks
                # ttl                  3600 # TTL for validation record
            }}
        }}
        # ---------- reverse-proxy targets ----------
        """
    )


def _render_wildcard(domain):
    """Render the wildcard domain for the reverse proxy."""
    return textwrap.dedent(
        f"""
        # Wild-card covering every sub-service in one cert
        *.{domain} {{
            # Reverse-proxy into the LAN
            root * /data/
            file_server
        }}
        """
    )


def get_subdomain(subdomain, domain, ip, port):
    """Get the subdomain for the reverse proxy."""
    return textwrap.dedent(
        f"""
        #-{subdomain}.{domain}-#
        {subdomain}.{domain} {r'{'}
            reverse_proxy {ip}:{port}
        {r'}'}"""
    )


def _render_reverse_proxy_targets(upstreams):
    r = []
    for upstream in upstreams:
        subdomain = upstream["subdomain"]
        domain = CONFIG.domain
        ip = upstream["ip"]
        port = upstream["port"]
        r.append(get_subdomain(subdomain, domain, ip, port))
    return "\n".join(r)


def render_caddyfile():
    """Render the Caddyfile from the templates."""
    global CONFIG
    out_str = ""
    out_str += _render_global_options(
        CONFIG.dns_provider, CONFIG.dns_token, CONFIG.email
    )
    out_str += _render_wildcard(CONFIG.domain)
    out_str += _render_reverse_proxy_targets(CONFIG.upstreams)
    with open(OUT, "w") as out_file:
        out_file.write(out_str)
    log.info(f"Rendered Caddyfile to {OUT}")


CONFIG = ReverseProxyConfig.from_file(CFG)


def main(force_build: bool = False):
    global CONFIG
    # 1) ------------------------------------------------------------------

    # 2) ------------------------------------------------------------------
    # Build only if binary missing (or we want --force-build CLI switch)
    if not BIN.exists() or force_build:
        log.info(f"Building Caddy with dns.providers.{CONFIG.dns_provider} …")
        build_caddy()
    elif not has_dns_plugin(CONFIG.dns_provider):
        log.warning(
            f"DNS provider {CONFIG.dns_provider} not found in current Caddy build, rebuilding …"
        )
        build_caddy()

    # 3) ------------------------------------------------------------------
    # Check if the configuration has changed
    render_caddyfile()

    # 4) ------------------------------------------------------------------
    print("Starting Caddy …")
    # Check if the Caddy binary is executable
    # if not os.access(BIN, os.X_OK):
    #     raise CaddyError(f"{BIN} is not executable")
    # # Check if the Caddy binary exists
    # if not os.path.exists(BIN):
    #     raise CaddyError(f"{BIN} does not exist")
    # run
    run(
        [
            str(BIN),
            "run",
            "--config",
            str(OUT),
            "--adapter",
            "caddyfile",
            "--watch",
            "--resume",
            "--environ",
            "CADDY_CONFIG_FILE=/tmp/Caddyfile",
            "CADDY_CONFIG_ADAPTER=caddyfile",
            "CADDY_CONFIG_WATCH=true",
            "CADDY_CONFIG_RESUME=true",
        ]
    )


if __name__ == "__main__":
    # Ensure build dir exists & GO cache writable
    WORK.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("GOMODCACHE", "/tmp/go/pkg/mod")
    os.environ.setdefault("GOCACHE", "/tmp/go/cache")
    os.environ.setdefault("GOPATH", "/tmp/go")
    os.environ.setdefault("GOBIN", "/tmp/go/bin")
    arg = argparse.ArgumentParser(
        "Caddy DNS-01 bootstrapper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # arg.add_argument(
    #     "force-build",
    #     help="Force build of Caddy even if binary exists",
    # )
    # arg.add_argument(
    #     "caddy",
    #     help="Run main, building Caddy if necessary",
    # )
    # arg.add_argument("config", help="Render current state and parsed config.yml")

    # arg.add_argument(
    #     "dns-token",
    #     help="DNS token for authentication",
    # )
    # args = arg.parse_args()
    # if args.caddy:
    main()
