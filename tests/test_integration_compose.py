import os
import shutil
import subprocess
import sys
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
    def test_print_caddyfile_compose_run(self):
        root = Path(__file__).resolve().parents[1]
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

        cmd = [
            "docker",
            "compose",
            "-f",
            "docker/docker-compose.yml",
            "-f",
            "docker/docker-compose.caddyfile.yml",
            "run",
            "--rm",
            "caddy",
        ]
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

        output = proc.stdout + "\n" + proc.stderr
        self.assertIn(f"status.{domain}", output)
        self.assertIn(f"{first_subdomain}.{domain}", output)


if __name__ == "__main__":
    unittest.main()
