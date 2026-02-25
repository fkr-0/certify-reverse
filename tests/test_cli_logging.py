import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from certify_reverse.cli import StripAnsiFormatter, hl


class CliLoggingTests(unittest.TestCase):
    def test_highlight_wraps_value_with_ansi(self):
        s = hl("example.com")
        self.assertTrue(s.startswith("\033["))
        self.assertIn("example.com", s)
        self.assertTrue(s.endswith("\033[0m"))

    def test_strip_ansi_formatter_removes_ansi_sequences(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Domain: %s",
            args=(hl("example.com"),),
            exc_info=None,
        )
        out = StripAnsiFormatter("%(message)s").format(record)
        self.assertEqual(out, "Domain: example.com")


if __name__ == "__main__":
    unittest.main()
