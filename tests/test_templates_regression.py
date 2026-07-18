import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from certify_reverse.templates import render_caddy, render_dnsmasq, render_status_index_html


class _Upstream:
    def __init__(self, subdomain, ip, port, scheme="http"):
        self.subdomain = subdomain
        self.ip = ip
        self.port = port
        self.scheme = scheme
        self.forward_auth_headers = True
        self.skip_verify = False
        self.trust_pool = None

    @property
    def is_https(self):
        return self.scheme == "https"


class _Cfg:
    email = "admin@example.com"
    dns_provider = "desec"
    dns_token = "token"
    dns_token_field = "api_token"
    domain = "example.com"
    dnsmasq_address_ip = "10.0.0.1"
    upstreams = [_Upstream("app", "10.0.0.10", 8080, "http")]


class TemplatesRegressionTests(unittest.TestCase):
    def test_render_status_index_html_escapes_js_template_vars(self):
        html = render_status_index_html(
            _Cfg(),
            {
                "domain": "example.com",
                "certify_reverse_version": "0.5.0",
                "certify_reverse_commit": "deadbee",
                "email": "admin@example.com",
                "dns_provider": "desec",
                "caddy_requested_version": "latest",
                "caddy_built_version": "v2.10.0",
                "caddy_latest_version": "v2.10.2",
                "caddy_update_recommended": True,
                "caddy_native_upgrade_supported": True,
                "generated_at": "2026-02-25 00:00:00",
            },
        )

        self.assertIn("${error.message}", html)
        self.assertIn("status.example.com/probe/app/", html)
        self.assertIn("Native upgrade", html)
        self.assertIn("certify-reverse v${version}", html)
        self.assertIn("Application commit", html)
        self.assertIn("crt.sh history", html)
        self.assertIn("fetchJson('/crtsh-state.json'", html)
        self.assertIn("/probe/crtsh?q=", html)
        self.assertIn("Certificate status", html)
        self.assertIn("Loading local crt.sh snapshot…", html)
        self.assertIn("Valid until", html)
        self.assertIn("Validity", html)
        self.assertIn("Last queried", html)
        self.assertIn("Run all checks", html)
        self.assertIn('<th scope="col">Ping</th>', html)
        self.assertIn('<th scope="col">TLS</th>', html)
        self.assertIn('<th scope="col">Actions</th>', html)

    def test_status_dashboard_includes_accessible_modern_ui_patterns(self):
        html = render_status_index_html(_Cfg(), {"domain": "example.com"})

        self.assertIn('class="skip-link" href="#main-content"', html)
        self.assertIn('<header class="site-header">', html)
        self.assertIn('<main class="shell stack" id="main-content" tabindex="-1">', html)
        self.assertIn('<nav class="section-nav" aria-label="Dashboard sections">', html)
        self.assertIn('role="status" aria-atomic="true"', html)
        self.assertIn('<caption>Configured reverse-proxy services', html)
        self.assertIn("lastElementChild.scope = 'row'", html)
        self.assertIn(':focus-visible', html)
        self.assertIn('--control-height: 44px', html)
        self.assertIn('@media (prefers-reduced-motion: reduce)', html)
        self.assertIn('@media (prefers-color-scheme: dark)', html)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('id="service-filter" type="search"', html)
        self.assertIn('id="history-filter" type="search"', html)
        self.assertIn('AbortController', html)
        self.assertIn('if (!response.ok)', html)
        self.assertIn("const ok = response.status < 500", html)
        self.assertIn("Response exceeds ${maxBytes} bytes", html)
        self.assertIn("response.body.getReader()", html)
        self.assertNotIn(".innerHTML", html)

    def test_status_dashboard_inline_javascript_has_valid_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is unavailable")

        html = render_status_index_html(_Cfg(), {"domain": "example.com"})
        match = re.search(r"<script>(.*?)</script>", html, re.S)
        self.assertIsNotNone(match)
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "dashboard.js"
            script.write_text(match.group(1), encoding="utf-8")
            result = subprocess.run(
                [node, "--check", str(script)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_render_status_index_html_cannot_close_inline_script_from_metadata(self):
        html = render_status_index_html(
            _Cfg(),
            {
                "email": "operator@example.com</script><script>alert(1)</script>",
                "domain": "example.com",
            },
        )

        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertIn(r"\u003c/script\u003e", html)

    def test_render_caddy_does_not_emit_unsupported_pki_options(self):
        caddyfile = render_caddy(_Cfg())
        self.assertNotIn("root_ca_ttl", caddyfile)
        self.assertNotIn("intermediate_ca_ttl", caddyfile)
        self.assertIn("tls {", caddyfile)
        self.assertIn("dns {$CADDY_DNS_PLUGIN}", caddyfile)
        self.assertIn("api_token {$CADDY_DNS_PLUGIN_TOKEN}", caddyfile)
        self.assertIn("propagation_delay 60s", caddyfile)
        self.assertIn("propagation_timeout 15m", caddyfile)
        self.assertIn("resolvers 1.1.1.1 8.8.8.8", caddyfile)
        self.assertIn("handle_path /probe/crtsh", caddyfile)
        self.assertEqual(caddyfile.count("header_up X-Real-IP {remote_host}"), 2)
        self.assertNotIn("header_up X-Real-IP {remote}", caddyfile)
        self.assertIn("handle /favicon.ico", caddyfile)
        self.assertNotIn(
            "app.example.com {\n    handle /favicon.ico",
            caddyfile,
        )

    def test_render_caddy_uses_configured_dns_token_field(self):
        class _CfgToken(_Cfg):
            dns_token_field = "token"

        caddyfile = render_caddy(_CfgToken())
        self.assertIn("token {$CADDY_DNS_PLUGIN_TOKEN}", caddyfile)
        self.assertNotIn("api_token {$CADDY_DNS_PLUGIN_TOKEN}", caddyfile)

    def test_render_caddy_brackets_ipv6_upstream_literals(self):
        class _CfgIpv6(_Cfg):
            upstreams = [_Upstream("app", "2001:db8::10", 8080, "http")]

        caddyfile = render_caddy(_CfgIpv6())
        self.assertIn("reverse_proxy http://[2001:db8::10]:8080", caddyfile)
        self.assertEqual(caddyfile.count("reverse_proxy http://[2001:db8::10]:8080"), 2)

    def test_internal_ca_endpoint_serves_exported_public_ca_files(self):
        caddyfile = render_caddy(_Cfg())
        self.assertIn("handle_path /cert/*", caddyfile)
        self.assertIn("root * /data/exported-certs", caddyfile)
        self.assertNotIn("reverse_proxy localhost:2021", caddyfile)

    def test_render_dnsmasq_logs_to_data_logs(self):
        conf = render_dnsmasq(_Cfg())
        self.assertIn("log-facility=/data/logs/dnsmasq.log", conf)
        self.assertIn("address=/.example.com/10.0.0.1", conf)

    def test_render_dnsmasq_uses_configured_target_ip(self):
        class _CfgCustom(_Cfg):
            dnsmasq_address_ip = "192.168.23.10"

        conf = render_dnsmasq(_CfgCustom())
        self.assertIn("address=/.example.com/192.168.23.10", conf)


if __name__ == "__main__":
    unittest.main()
