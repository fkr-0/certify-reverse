import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from certify_reverse.templates import render_status_index_html


class _Upstream:
    def __init__(self, subdomain, ip, port, scheme="http"):
        self.subdomain = subdomain
        self.ip = ip
        self.port = port
        self.scheme = scheme


class _Cfg:
    domain = "example.com"
    upstreams = [_Upstream("app", "10.0.0.10", 8080, "http")]


class TemplatesRegressionTests(unittest.TestCase):
    def test_render_status_index_html_escapes_js_template_vars(self):
        html = render_status_index_html(
            _Cfg(),
            {
                "domain": "example.com",
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


if __name__ == "__main__":
    unittest.main()
