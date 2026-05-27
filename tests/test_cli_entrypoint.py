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


if __name__ == "__main__":
    unittest.main()
