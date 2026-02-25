import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli


class CliBuildTests(unittest.TestCase):
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
                    captured["cmd"] = cmd
                    captured["env"] = kw.get("env", {})
                    captured["cwd"] = kw.get("cwd")
                    out_path = Path(cmd[cmd.index("--output") + 1])
                    out_path.write_text("new-binary", encoding="utf-8")
                    return ""

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
