import sys
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

        self.assertIn("${e.message}", html)
        self.assertIn("status.example.com/probe/app/", html)
        self.assertIn("Native Upgrade Cmd", html)
        self.assertIn("certify-reverse v${appVer} Dashboard", html)
        self.assertIn("certify-reverse commit:", html)
        self.assertIn("crt.sh Certificate History", html)
        self.assertIn("fetch('/crtsh-state.json'", html)
        self.assertIn("/probe/crtsh?q=", html)
        self.assertIn("crt.sh Status", html)
        self.assertIn("Querying crt.sh status...", html)
        self.assertIn("Latest Valid Until", html)
        self.assertIn("Certificate Validity", html)
        self.assertIn("Last Queried", html)
        self.assertIn("↻ Refresh", html)
        self.assertIn("<th>Ping</th>", html)
        self.assertIn("<th>Cert</th>", html)
        self.assertNotIn("<th>Status</th>", html)
        self.assertNotIn("<th>Actions</th>", html)

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
