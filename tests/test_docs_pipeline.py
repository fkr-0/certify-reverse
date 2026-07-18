import importlib.util
import py_compile
import re
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_docs_build_module():
    script = ROOT / "tools" / "docs" / "build.py"
    spec = importlib.util.spec_from_file_location("docs_build", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocsPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load_docs_build_module()

    def test_mkdocs_uses_material_and_explicit_search(self):
        config = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))

        self.assertEqual(config["theme"]["name"], "material")
        self.assertTrue(config["strict"])
        self.assertIn("search.suggest", config["theme"]["features"])
        self.assertIn("search.highlight", config["theme"]["features"])
        plugin_names = [
            item if isinstance(item, str) else next(iter(item))
            for item in config["plugins"]
        ]
        self.assertIn("search", plugin_names)
        self.assertIn("Documentation publishing", str(config["nav"]))

    def test_handbook_sources_and_man_sources_exist(self):
        config = tomllib.loads(
            (ROOT / "tools" / "docs" / "handbook.toml").read_text(encoding="utf-8")
        )

        self.assertGreaterEqual(len(config["chapters"]), 10)
        for value in config["chapters"]:
            path = ROOT / value
            self.assertTrue(path.is_file(), value)
            self.assertIn("# ", path.read_text(encoding="utf-8"), value)
        for entry in config["man_pages"]:
            source = ROOT / entry["source"]
            self.assertTrue(source.is_file(), source)
            content = source.read_text(encoding="utf-8")
            self.assertIn("section: 1", content)
            self.assertIn("@VERSION@", content)

    def test_python_docs_lock_is_fully_pinned_and_hashed(self):
        lock = (ROOT / "tools" / "docs" / "requirements.lock.txt").read_text(
            encoding="utf-8"
        )
        requirements = re.findall(r"^([a-z0-9][a-z0-9._-]*)==([^ \\\n]+)", lock, re.M)

        self.assertGreaterEqual(len(requirements), 10)
        self.assertIn("--hash=sha256:", lock)
        self.assertNotRegex(lock, r"^[a-z0-9][a-z0-9._-]*\s*(?:>=|~=|<)", re.M)

    def test_documentation_toolchain_pins_python_uv_and_renderers(self):
        toolchain = tomllib.loads(
            (ROOT / "tools" / "docs" / "toolchain.toml").read_text(encoding="utf-8")
        )

        self.assertRegex(toolchain["python"]["version"], r"^\d+\.\d+$")
        self.assertRegex(toolchain["package_manager"]["uv"], r"^\d+\.\d+\.\d+$")
        for renderer in ("pandoc", "weasyprint", "groff"):
            self.assertRegex(toolchain["renderers"][renderer], r"^\d+(?:\.\d+)+$")

    def test_invalid_source_date_epoch_has_actionable_error(self):
        with mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "not-a-number"}):
            with self.assertRaisesRegex(self.module.DocsBuildError, "SOURCE_DATE_EPOCH"):
                self.module.source_date()

    def test_internal_markdown_links_are_rewritten_for_handbook(self):
        module = self.module
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "guide.md"
            target = root / "configuration.md"
            source.write_text(
                "# Guide\n\nRead [configuration](configuration.md) and "
                "[ports](configuration.md#ports).\n",
                encoding="utf-8",
            )
            target.write_text("# Configuration\n\n## Ports\n", encoding="utf-8")
            rewritten = module.rewrite_markdown_links(
                source.read_text(encoding="utf-8"),
                source=source,
                anchors={target.resolve(): "configuration"},
            )

        self.assertIn("[configuration](#configuration)", rewritten)
        self.assertIn("[ports](#ports)", rewritten)

    def test_handbook_chapter_gets_explicit_renderer_independent_anchor(self):
        anchored = self.module.add_explicit_chapter_anchor(
            "# Tutorial: WordPress + Telegram webhook\n\nBody.\n",
            "tutorial-wordpress-telegram-webhook",
        )

        self.assertIn(
            "# Tutorial: WordPress + Telegram webhook {#tutorial-wordpress-telegram-webhook}",
            anchored,
        )

    def test_beginner_paths_include_expected_results_and_cleanup(self):
        quickstart = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
        tutorial = (
            ROOT / "docs" / "tutorials" / "wordpress-telegram.md"
        ).read_text(encoding="utf-8")

        self.assertGreaterEqual(quickstart.count("**Expected:**"), 4)
        self.assertIn("Clean up", quickstart)
        self.assertIn("curl --resolve", quickstart)
        self.assertGreaterEqual(tutorial.count("**Expected:**"), 3)
        self.assertIn("down --volumes", tutorial)
        self.assertIn("X-Telegram-Bot-Api-Secret-Token", tutorial)

    def test_example_yaml_and_python_are_syntactically_valid(self):
        yaml_paths = [
            ROOT / "examples" / "quickstart" / "compose.override.yml",
            ROOT / "examples" / "wordpress-telegram" / "compose.override.yml",
            ROOT / "examples" / "wordpress-telegram" / "upstreams.yml",
        ]
        for path in yaml_paths:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict, path)

        app = ROOT / "examples" / "wordpress-telegram" / "telegram-bot" / "app.py"
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(app, cfile=str(Path(tmp) / "app.pyc"), doraise=True)

        result = subprocess.run(
            ["sh", "-n", str(ROOT / "examples" / "wordpress-telegram" / "register-webhook.sh")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_project_helper_exposes_docs_commands_without_docker_dispatch(self):
        script = (ROOT / "caddy-docker.sh").read_text(encoding="utf-8")

        for command in (
            "docs)",
            "docs-check)",
            "docs-site)",
            "docs-serve)",
            "docs-clean)",
            "docs-update-lock)",
        ):
            self.assertIn(command, script)
        self.assertIn("python3 tools/docs/build.py check", script)


if __name__ == "__main__":
    unittest.main()
