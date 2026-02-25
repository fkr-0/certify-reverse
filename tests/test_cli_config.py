import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from certify_reverse.cli import InvalidSetupError, load_upstreams, must_env


class CliConfigTests(unittest.TestCase):
    def test_must_env_missing_raises_invalid_setup(self):
        key = "DNS_PROVIDER"
        old = os.environ.pop(key, None)
        try:
            with self.assertRaises(InvalidSetupError):
                must_env(key)
        finally:
            if old is not None:
                os.environ[key] = old

    def test_load_upstreams_top_level_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "upstreams.yml"
            p.write_text("app:\n  ip: 10.0.0.1\n  port: 8080\n", encoding="utf-8")
            upstreams = load_upstreams(p)
            self.assertEqual(len(upstreams), 1)
            self.assertEqual(upstreams[0].subdomain, "app")
            self.assertEqual(upstreams[0].ip, "10.0.0.1")
            self.assertEqual(upstreams[0].port, 8080)

    def test_load_upstreams_invalid_shape_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "upstreams.yml"
            p.write_text("- subdomain: app\n", encoding="utf-8")
            with self.assertRaises(InvalidSetupError):
                load_upstreams(p)


if __name__ == "__main__":
    unittest.main()
