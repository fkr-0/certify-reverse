import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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


if __name__ == "__main__":
    unittest.main()
