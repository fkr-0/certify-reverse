import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli


class CliBuildTests(unittest.TestCase):
    def test_caddy_has_plugin_requires_exact_module_name(self):
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.CADDY = Path(tmp) / "caddy-rebuild"
                cli.CADDY.write_text("dummy", encoding="utf-8")
                with mock.patch.object(
                    cli,
                    "run",
                    return_value="dns.providers.desec-extra\ndns.providers.cloudflare\n",
                ):
                    self.assertFalse(cli.caddy_has_plugin("desec"))
                with mock.patch.object(cli, "run", return_value="dns.providers.desec\n"):
                    self.assertTrue(cli.caddy_has_plugin("desec"))
        finally:
            cli.CADDY = old_caddy

    def test_update_check_degrades_cleanly_on_timeout(self):
        with (
            mock.patch.object(cli, "get_built_caddy_version", return_value="v2.10.0"),
            mock.patch.object(cli, "get_latest_caddy_version", side_effect=TimeoutError("offline")),
        ):
            status = cli.check_caddy_update_status()

        self.assertEqual(status["latest"], "unavailable")
        self.assertIsNone(status["recommended"])
        self.assertIn("offline", status["error"])

    def test_explicit_caddy_version_must_match_installed_binary(self):
        with mock.patch.object(cli, "get_caddy_version", return_value="v2.10.0 h1:abc"):
            self.assertTrue(cli.caddy_matches_requested_version("v2.10.0"))
            self.assertTrue(cli.caddy_matches_requested_version("2.10.0"))
            self.assertFalse(cli.caddy_matches_requested_version("v2.10.1"))
            self.assertTrue(cli.caddy_matches_requested_version("latest"))

    def test_prerelease_caddy_version_requires_exact_match(self):
        with mock.patch.object(cli, "get_caddy_version", return_value="v2.11.0-beta.1"):
            self.assertTrue(cli.caddy_matches_requested_version("v2.11.0-beta.1"))
            self.assertFalse(cli.caddy_matches_requested_version("v2.11.0-beta.2"))

    def test_build_caddy_uses_writable_caches_and_replaces_binary_atomically(self):
        old_work = cli.WORK
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                cli.WORK = td / "work"
                cli.CADDY = td / "caddy-rebuild"
                cli.WORK.mkdir(parents=True, exist_ok=True)
                cli.CADDY.write_text("old-binary", encoding="utf-8")

                captured = {}

                def fake_run(cmd, **kw):
                    if cmd[0] == "xcaddy":
                        captured["cmd"] = cmd
                        captured["env"] = kw.get("env", {})
                        captured["cwd"] = kw.get("cwd")
                        out_path = Path(cmd[cmd.index("--output") + 1])
                        out_path.write_text("new-binary", encoding="utf-8")
                        out_path.chmod(0o755)
                        return ""
                    if cmd[1] == "list-modules":
                        return "dns.providers.desec\n"
                    if cmd[1] == "version":
                        return "v2.10.0 h1:abc\n"
                    raise AssertionError(cmd)

                with mock.patch.object(cli, "run", side_effect=fake_run):
                    cli.build_caddy("desec", "v2.10.0")

                self.assertEqual(captured["cmd"][0], "xcaddy")
                self.assertIn("v2.10.0", captured["cmd"])
                self.assertEqual(captured["cwd"], cli.WORK)
                self.assertEqual(captured["env"]["HOME"], str(cli.WORK))
                self.assertEqual(captured["env"]["GOTOOLCHAIN"], "auto")
                self.assertEqual(captured["env"]["XCADDY_SETCAP"], "0")
                self.assertTrue(captured["env"]["GOCACHE"].startswith(str(cli.WORK)))
                self.assertTrue(captured["env"]["GOMODCACHE"].startswith(str(cli.WORK)))
                self.assertTrue(captured["env"]["XDG_CACHE_HOME"].startswith(str(cli.WORK)))
                self.assertEqual(cli.CADDY.read_text(encoding="utf-8"), "new-binary")
        finally:
            cli.WORK = old_work
            cli.CADDY = old_caddy

    def test_build_caddy_rejects_unvalidated_binary_and_preserves_existing_one(self):
        old_work = cli.WORK
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                cli.WORK = td / "work"
                cli.CADDY = td / "caddy-rebuild"
                cli.WORK.mkdir(parents=True, exist_ok=True)
                cli.CADDY.write_text("known-good", encoding="utf-8")

                def fake_run(cmd, **kw):
                    if cmd[0] == "xcaddy":
                        out_path = Path(cmd[cmd.index("--output") + 1])
                        out_path.write_text("bad-build", encoding="utf-8")
                        out_path.chmod(0o755)
                        return ""
                    if cmd[1] == "list-modules":
                        return "dns.providers.cloudflare\n"
                    if cmd[1] == "version":
                        return "v2.10.0\n"
                    raise AssertionError(cmd)

                with (
                    mock.patch.object(cli, "run", side_effect=fake_run),
                    self.assertRaisesRegex(RuntimeError, "missing required module"),
                ):
                    cli.build_caddy("desec", "v2.10.0")

                self.assertEqual(cli.CADDY.read_text(encoding="utf-8"), "known-good")
                self.assertFalse((cli.WORK / "caddy-rebuild.new").exists())
        finally:
            cli.WORK = old_work
            cli.CADDY = old_caddy

    def test_format_caddyfile_content_uses_caddy_fmt_when_available(self):
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                cli.CADDY = td / "caddy-rebuild"
                cli.CADDY.write_text("dummy", encoding="utf-8")
                with mock.patch("subprocess.run") as m_run:
                    m_run.return_value = mock.Mock(returncode=0, stdout="{\n\temail a@b\n}\n")
                    out = cli.format_caddyfile_content("{ email a@b }")
                    self.assertIn("email a@b", out)
                    self.assertTrue(out.endswith("\n"))
        finally:
            cli.CADDY = old_caddy


if __name__ == "__main__":
    unittest.main()
