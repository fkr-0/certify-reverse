import shutil
import subprocess
import unittest
from pathlib import Path

import yaml


def _docker_compose_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return r.returncode == 0


def _load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@unittest.skipUnless(_docker_compose_available(), "docker compose not available")
class ComposeIntegrationTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def _current_source_run(self, *python_args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "-f",
            "docker/docker-compose.yml",
            "run",
            "--rm",
            "--no-deps",
            "-v",
            f"{self.root / 'src'}:/checkout/src:ro",
            "-e",
            "PYTHONPATH=/checkout/src",
            "--entrypoint",
            "python3",
            "caddy",
            *python_args,
        ]

    def test_container_imports_current_checkout_source(self):
        proc = subprocess.run(
            self._current_source_run(
                "-c",
                "import certify_reverse; print(certify_reverse.__file__)",
            ),
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("/checkout/src/certify_reverse/__init__.py", proc.stdout)

    def test_print_caddyfile_compose_run(self):
        root = self.root
        env_file = root / ".env"
        upstreams_file = root / "upstreams.yml"

        if not env_file.exists() or not upstreams_file.exists():
            self.skipTest(".env or upstreams.yml missing")

        env_data = _load_env(env_file)
        domain = env_data.get("DOMAIN")
        self.assertTrue(domain, "DOMAIN must be set in .env")

        upstreams_data = yaml.safe_load(upstreams_file.read_text(encoding="utf-8")) or {}
        self.assertIsInstance(upstreams_data, dict)
        self.assertGreater(len(upstreams_data), 0)
        first_subdomain = next(iter(upstreams_data.keys()))

        cmd = self._current_source_run("-m", "certify_reverse.cli", "--print-caddyfile")
        proc = subprocess.run(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
            check=False,
        )

        if proc.returncode != 0:
            self.fail(
                "compose integration run failed\n"
                f"returncode={proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )

        self.assertTrue(proc.stdout.lstrip().startswith("{"), proc.stdout)
        self.assertIn(f"status.{domain}", proc.stdout)
        self.assertIn(f"{first_subdomain}.{domain}", proc.stdout)

    def test_generated_caddyfile_validates_with_bundled_caddy(self):
        cmd = [
            "docker",
            "compose",
            "-f",
            "docker/docker-compose.yml",
            "run",
            "--rm",
            "--no-deps",
            "-v",
            f"{self.root / 'src'}:/checkout/src:ro",
            "-e",
            "PYTHONPATH=/checkout/src",
            "--entrypoint",
            "python3",
            "caddy",
            "-c",
            "import os, subprocess; "
            "from pathlib import Path; "
            "from certify_reverse.cli import CADDY, ReverseProxyConfig; "
            "from certify_reverse.templates import render_caddy, set_datadir; "
            "set_datadir(Path('/data')); "
            "cfg = ReverseProxyConfig.from_sources(); "
            "os.environ['CADDY_DNS_PLUGIN'] = cfg.dns_provider; "
            "os.environ['CADDY_DNS_PLUGIN_TOKEN'] = cfg.dns_token; "
            "Path('/tmp/Caddyfile').write_text(render_caddy(cfg), encoding='utf-8'); "
            "subprocess.run([str(CADDY), 'validate', '--config', '/tmp/Caddyfile', "
            "'--adapter', 'caddyfile'], check=True)",
        ]
        proc = subprocess.run(
            cmd,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
            check=False,
        )

        self.assertEqual(
            proc.returncode,
            0,
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}",
        )

    def test_env_file_overrides_inherited_caddy_version(self):
        root = self.root
        env_file = root / ".env"
        if not env_file.exists():
            self.skipTest(".env missing")

        env_data = _load_env(env_file)
        expected = env_data.get("CADDY_VERSION")
        if not expected:
            self.skipTest("CADDY_VERSION missing in .env")

        cmd = self._current_source_run(
            "-c",
            "from certify_reverse.cli import ReverseProxyConfig; print(ReverseProxyConfig.from_sources().caddy_version)",
        )
        caddy_index = cmd.index("caddy")
        cmd[caddy_index:caddy_index] = ["-e", "CADDY_VERSION=v2.10.0"]
        proc = subprocess.run(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )

        if proc.returncode != 0:
            self.fail(
                "compose env precedence integration run failed\n"
                f"returncode={proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )

        out = (proc.stdout + "\n" + proc.stderr).strip()
        self.assertIn(expected, out)


if __name__ == "__main__":
    unittest.main()
