import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli
from certify_reverse.cli import _crtsh_latest


class CliCrtShTests(unittest.TestCase):
    def test_crtsh_latest_selects_newest_not_after_and_validity(self):
        entries = [
            {"id": 1, "not_before": "2024-01-01", "not_after": "2025-01-01"},
            {"id": 2, "not_before": "2025-01-01", "not_after": "2099-01-01"},
        ]
        latest, validity = _crtsh_latest(entries)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["id"], 2)
        self.assertEqual(validity, "valid")

    def test_crtsh_latest_handles_empty(self):
        latest, validity = _crtsh_latest([])
        self.assertIsNone(latest)
        self.assertEqual(validity, "none")

    def test_status_assets_degrade_cleanly_on_crtsh_transport_failure(self):
        old_values = {
            name: getattr(cli, name)
            for name in ("DATADIR", "INDEX_HTML", "ACME_STATE_JSON", "CRTSH_STATE_JSON")
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                cli.DATADIR = td
                cli.INDEX_HTML = td / "index.html"
                cli.ACME_STATE_JSON = td / "acme-state.json"
                cli.CRTSH_STATE_JSON = td / "crtsh-state.json"
                cli.set_datadir(td)
                cfg = cli.ReverseProxyConfig(
                    dns_provider="desec",
                    dns_token="secret",
                    email="admin@example.com",
                    domain="example.com",
                    upstreams=[cli.Upstream("app", "10.0.0.2", 8080)],
                )

                with (
                    mock.patch.object(cli, "write_static_assets"),
                    mock.patch.object(
                        cli,
                        "check_caddy_update_status",
                        return_value={
                            "built": "v2.10.0",
                            "latest": "unavailable",
                            "recommended": None,
                            "native_upgrade_supported": False,
                        },
                    ),
                    mock.patch.object(cli, "fetch_crtsh_state", side_effect=OSError("reset")),
                ):
                    cli.write_status_assets(cfg)

                state = json.loads(cli.CRTSH_STATE_JSON.read_text(encoding="utf-8"))
                self.assertEqual(state["match_count"], 0)
                self.assertIn("reset", state["error"])
                self.assertTrue(cli.INDEX_HTML.exists())
        finally:
            for name, value in old_values.items():
                setattr(cli, name, value)
            cli.set_datadir(old_values["DATADIR"])


if __name__ == "__main__":
    unittest.main()
