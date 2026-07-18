import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli
from certify_reverse.cli import (
    InvalidSetupError,
    derive_dnsmasq_address_ip,
    env_first,
    is_ipv4,
    load_env_file,
    load_upstreams,
    must_env,
)


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

    def test_load_env_file_rejects_invalid_environment_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".env"
            p.write_text("BAD-KEY=value\n", encoding="utf-8")
            with self.assertRaisesRegex(InvalidSetupError, "Invalid environment key"):
                load_env_file(p)

    def test_atomic_text_write_preserves_existing_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text("old", encoding="utf-8")
            p.chmod(0o640)

            cli._atomic_write_text(p, "new")

            self.assertEqual(p.read_text(encoding="utf-8"), "new")
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)
            self.assertEqual(list(p.parent.glob(f".{p.name}.*.tmp")), [])

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

    def test_load_upstreams_rejects_path_traversal_subdomain(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "upstreams.yml"
            p.write_text("../../escaped:\n  ip: 10.0.0.1\n  port: 8080\n", encoding="utf-8")
            with self.assertRaisesRegex(InvalidSetupError, "invalid DNS label"):
                load_upstreams(p)

    def test_load_upstreams_rejects_invalid_scheme_and_port(self):
        invalid_specs = (
            "app:\n  ip: 10.0.0.1\n  port: 0\n",
            "app:\n  ip: 10.0.0.1\n  port: 8080\n  scheme: ftp\n",
        )
        for content in invalid_specs:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "upstreams.yml"
                p.write_text(content, encoding="utf-8")
                with self.assertRaises(InvalidSetupError):
                    load_upstreams(p)

    def test_load_upstreams_rejects_unknown_fields_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "upstreams.yml"
            p.write_text(
                "app:\n  ip: 10.0.0.1\n  port: 8080\n  unsupported: true\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(InvalidSetupError, "Invalid fields"):
                load_upstreams(p)

    def test_load_upstreams_rejects_normalized_name_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "upstreams.yml"
            p.write_text(
                "App:\n  ip: 10.0.0.1\n  port: 8080\n"
                "app:\n  ip: 10.0.0.2\n  port: 8081\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(InvalidSetupError, "normalize to the same name"):
                load_upstreams(p)

    def test_load_env_file_overrides_preexisting_env(self):
        key = "CADDY_VERSION"
        old = os.environ.get(key)
        os.environ[key] = "v2.10.0"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / ".env"
                p.write_text("CADDY_VERSION=v2.11.1\n", encoding="utf-8")
                load_env_file(p)
                self.assertEqual(os.environ.get(key), "v2.11.1")
        finally:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_prepare_caddy_runtime_env_sets_writable_xdg_paths(self):
        old_datadir = cli.DATADIR
        old_env = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.DATADIR = Path(tmp)
                cli.prepare_caddy_runtime_env()
                self.assertEqual(os.environ["HOME"], str(cli.DATADIR))
                self.assertEqual(os.environ["XDG_CONFIG_HOME"], str(cli.DATADIR / ".config"))
                self.assertEqual(os.environ["XDG_DATA_HOME"], str(cli.DATADIR / ".local" / "share"))
                self.assertEqual(os.environ["XDG_CACHE_HOME"], str(cli.DATADIR / ".cache"))
        finally:
            cli.DATADIR = old_datadir
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_write_static_assets_writes_favicon_into_datadir(self):
        old_datadir = cli.DATADIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.DATADIR = Path(tmp)
                cli.write_static_assets()
                favicon = cli.DATADIR / "favicon.ico"
                self.assertTrue(favicon.exists())
                self.assertGreater(favicon.stat().st_size, 0)
        finally:
            cli.DATADIR = old_datadir

    def test_env_first_accepts_upper_and_lower_case_keys(self):
        keys = ("DNSMASQ_ADDRESS_IP", "dnsmasq_address_ip")
        old = {k: os.environ.get(k) for k in keys}
        try:
            os.environ.pop("DNSMASQ_ADDRESS_IP", None)
            os.environ["dnsmasq_address_ip"] = "192.168.1.50"
            self.assertEqual(env_first("DNSMASQ_ADDRESS_IP", "dnsmasq_address_ip", default="10.0.0.1"), "192.168.1.50")

            os.environ["DNSMASQ_ADDRESS_IP"] = "10.10.10.10"
            self.assertEqual(env_first("DNSMASQ_ADDRESS_IP", "dnsmasq_address_ip", default="10.0.0.1"), "10.10.10.10")
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_derive_dnsmasq_address_ip_host_src_ip_success(self):
        with mock.patch("subprocess.check_output", return_value="1.1.1.1 via 192.168.1.1 dev eth0 src 192.168.1.50 uid 0\n"):
            out = derive_dnsmasq_address_ip("host-src-ip", "10.0.0.1")
            self.assertEqual(out, "192.168.1.50")

    def test_derive_dnsmasq_address_ip_host_src_ip_fallback(self):
        with (
            mock.patch("subprocess.check_output", side_effect=OSError("ip failed")),
            mock.patch.object(cli.log, "warning"),
        ):
            out = derive_dnsmasq_address_ip("host-src-ip", "10.0.0.1")
            self.assertEqual(out, "10.0.0.1")

    def test_derive_dnsmasq_address_ip_rejects_unknown_mode(self):
        with self.assertRaisesRegex(InvalidSetupError, "DNSMASQ_ADDRESS_MODE"):
            derive_dnsmasq_address_ip("surprise", "10.0.0.1")

    def test_derive_dnsmasq_address_ip_prefers_host_override(self):
        key = "HOST_DNSMASQ_ADDRESS_IP"
        old = os.environ.get(key)
        try:
            os.environ[key] = "192.168.23.156"
            out = derive_dnsmasq_address_ip("host-src-ip", "10.0.0.1")
            self.assertEqual(out, "192.168.23.156")
        finally:
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def test_is_ipv4_rejects_invalid_octets(self):
        self.assertFalse(is_ipv4("999.999.999.999"))
        self.assertFalse(is_ipv4("256.1.1.1"))
        self.assertTrue(is_ipv4("192.168.1.1"))

    def test_reverse_proxy_config_rejects_empty_caddy_version(self):
        with self.assertRaisesRegex(InvalidSetupError, "CADDY_VERSION"):
            cli.ReverseProxyConfig(
                dns_provider="desec",
                dns_token="secret",
                email="admin@example.com",
                domain="example.com",
                caddy_version="",
            )

    def test_reverse_proxy_config_rejects_non_version_caddy_reference(self):
        with self.assertRaisesRegex(InvalidSetupError, "semantic version"):
            cli.ReverseProxyConfig(
                dns_provider="desec",
                dns_token="secret",
                email="admin@example.com",
                domain="example.com",
                caddy_version="--output",
            )

    def test_reverse_proxy_config_normalizes_bare_caddy_version(self):
        cfg = cli.ReverseProxyConfig(
            dns_provider="desec",
            dns_token="secret",
            email="admin@example.com",
            domain="example.com",
            caddy_version="2.10.0",
        )
        self.assertEqual(cfg.caddy_version, "v2.10.0")

    def test_reverse_proxy_config_uses_provider_credential_default(self):
        desec = cli.ReverseProxyConfig(
            dns_provider="desec",
            dns_token="secret",
            email="admin@example.com",
            domain="example.com",
        )
        unknown = cli.ReverseProxyConfig(
            dns_provider="custom-provider",
            dns_token="secret",
            email="admin@example.com",
            domain="example.com",
        )
        self.assertEqual(desec.dns_token_field, "token")
        self.assertEqual(unknown.dns_token_field, "api_token")

    def test_reverse_proxy_config_rejects_whitespace_only_dns_token(self):
        with self.assertRaisesRegex(InvalidSetupError, "DNS_TOKEN"):
            cli.ReverseProxyConfig(
                dns_provider="desec",
                dns_token="   ",
                email="admin@example.com",
                domain="example.com",
            )

    def test_reverse_proxy_config_rejects_reserved_generated_hosts(self):
        for subdomain in ("status", "internal-ca"):
            with self.subTest(subdomain=subdomain), self.assertRaisesRegex(
                InvalidSetupError, "reserved"
            ):
                cli.ReverseProxyConfig(
                    dns_provider="desec",
                    dns_token="secret",
                    email="admin@example.com",
                    domain="example.com",
                    upstreams=[cli.Upstream(subdomain, "10.0.0.2", 8080)],
                )

    def test_reverse_proxy_config_validates_direct_dnsmasq_mode(self):
        with self.assertRaisesRegex(InvalidSetupError, "DNSMASQ_ADDRESS_MODE"):
            cli.ReverseProxyConfig(
                dns_provider="desec",
                dns_token="secret",
                email="admin@example.com",
                domain="example.com",
                dnsmasq_address_mode="invalid",
            )


if __name__ == "__main__":
    unittest.main()
