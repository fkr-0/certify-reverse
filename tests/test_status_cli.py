import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.status_cli as status_cli


class StatusCliTests(unittest.TestCase):
    def test_data_dir_option_selects_directory_to_inspect(self):
        old_datadir = status_cli.DATADIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with (
                    mock.patch.object(
                        sys,
                        "argv",
                        ["certify-reverse-status", "--data-dir", tmp, "--data"],
                    ),
                    mock.patch.object(status_cli, "show_data_directory_overview") as show_data,
                ):
                    status_cli.main()

                self.assertEqual(status_cli.DATADIR, Path(tmp).resolve())
                show_data.assert_called_once_with()
        finally:
            status_cli.DATADIR = old_datadir


if __name__ == "__main__":
    unittest.main()
