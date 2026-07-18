import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _link_commands(bin_dir: Path, *commands: str) -> None:
    for command in commands:
        source = shutil.which(command)
        if source is None:
            raise unittest.SkipTest(f"required test command is unavailable: {command}")
        (bin_dir / command).symlink_to(source)


class ShellHelperTests(unittest.TestCase):
    def test_version_command_does_not_require_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "caddy-docker.sh"
            shutil.copy2(ROOT / "caddy-docker.sh", script)
            shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            _link_commands(bin_dir, "dirname", "sed")

            result = subprocess.run(
                ["/bin/bash", str(script), "version"],
                cwd=root,
                env={"PATH": str(bin_dir)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "0.5.2")

    def test_config_command_redacts_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "caddy-docker.sh"
            shutil.copy2(ROOT / "caddy-docker.sh", script)
            shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
            (root / ".env").write_text(
                "DNS_TOKEN=do-not-print\nDOMAIN=example.com\n",
                encoding="utf-8",
            )
            (root / "upstreams.yml").write_text(
                "app:\n  ip: backend\n  port: 8080\n  ext_params:\n    api_key: yaml-secret\n",
                encoding="utf-8",
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            _link_commands(bin_dir, "cat", "dirname", "id", "sed")
            fake_docker = bin_dir / "docker"
            fake_docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_docker.chmod(0o755)

            result = subprocess.run(
                ["/bin/bash", str(script), "config"],
                cwd=root,
                env={"PATH": str(bin_dir)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("do-not-print", result.stdout)
            self.assertNotIn("yaml-secret", result.stdout)
            self.assertIn("DNS_TOKEN=***REDACTED***", result.stdout)
            self.assertIn("api_key: ***REDACTED***", result.stdout)
            self.assertIn("DOMAIN=example.com", result.stdout)


if __name__ == "__main__":
    unittest.main()
