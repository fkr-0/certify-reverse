import importlib.util
import tempfile
import tomllib
import unittest
from pathlib import Path

import certify_reverse


ROOT = Path(__file__).resolve().parents[1]


def _load_bump_module():
    script = ROOT / "scripts" / "bump_version.py"
    spec = importlib.util.spec_from_file_location("bump_version", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VersioningTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self):
        with (ROOT / "pyproject.toml").open("rb") as f:
            project_version = tomllib.load(f)["project"]["version"]
        self.assertEqual(certify_reverse.__version__, project_version)

    def test_bump_script_updates_both_version_sources(self):
        module = _load_bump_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pyproject = root / "pyproject.toml"
            package_init = root / "__init__.py"
            pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
            package_init.write_text('__version__ = "0.0.1"\n', encoding="utf-8")

            result = module.bump_version("patch", pyproject, package_init)

            self.assertEqual(result, "1.2.4")
            self.assertIn('version = "1.2.4"', pyproject.read_text(encoding="utf-8"))
            self.assertIn('__version__ = "1.2.4"', package_init.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
