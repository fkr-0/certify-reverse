import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli
from certify_reverse.cli import InvalidSetupError


class CliEntrypointTests(unittest.TestCase):
    def test_entrypoint_exits_nonzero_on_invalid_setup(self):
        old_work = cli.WORK
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.WORK = Path(tmp) / "work"
                opts = SimpleNamespace(
                    check_updates=False,
                    export_certs=False,
                    create_service_dirs=False,
                    force_build=False,
                    rebuild_caddy=False,
                    rebuild_caddy_only=False,
                    update_caddy=False,
                    show_certs=False,
                    print_caddyfile=False,
                )
                with (
                    mock.patch.object(cli, "configure_logging"),
                    mock.patch("argparse.ArgumentParser.parse_args", return_value=opts),
                    mock.patch.object(cli, "main", side_effect=InvalidSetupError("bad config")),
                ):
                    with self.assertRaises(SystemExit) as cm:
                        cli.entrypoint()
                self.assertEqual(cm.exception.code, 1)
        finally:
            cli.WORK = old_work

    def test_rebuild_only_exits_after_validated_build_without_starting_caddy(self):
        old_work = cli.WORK
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.WORK = Path(tmp) / "work"
                opts = SimpleNamespace(
                    check_updates=False,
                    export_certs=False,
                    create_service_dirs=False,
                    force_build=False,
                    rebuild_caddy=False,
                    rebuild_caddy_only=True,
                    update_caddy=False,
                    show_certs=False,
                    print_caddyfile=False,
                )
                cfg = mock.Mock(dns_provider="desec", caddy_version="v2.10.0")
                with (
                    mock.patch.object(cli, "configure_logging"),
                    mock.patch("argparse.ArgumentParser.parse_args", return_value=opts),
                    mock.patch.object(cli.ReverseProxyConfig, "from_sources", return_value=cfg),
                    mock.patch.object(cli, "build_caddy") as build,
                    mock.patch.object(cli, "get_built_caddy_version", return_value="v2.10.0"),
                    mock.patch.object(cli, "main") as runtime_main,
                    self.assertRaises(SystemExit) as cm,
                ):
                    cli.entrypoint()

                self.assertEqual(cm.exception.code, 0)
                build.assert_called_once_with("desec", "v2.10.0")
                runtime_main.assert_not_called()
        finally:
            cli.WORK = old_work


if __name__ == "__main__":
    unittest.main()
