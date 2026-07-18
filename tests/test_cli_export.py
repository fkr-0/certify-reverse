import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli


class CliExportTests(unittest.TestCase):
    def test_generated_service_private_key_is_restricted_and_replaced(self):
        old_datadir = cli.DATADIR
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.DATADIR = Path(tmp)
                cli.CADDY = cli.DATADIR / "caddy-rebuild"
                cli.CADDY.write_text("binary", encoding="utf-8")
                cfg = cli.ReverseProxyConfig(
                    dns_provider="desec",
                    dns_token="secret",
                    email="admin@example.com",
                    domain="example.com",
                    upstreams=[cli.Upstream("app", "10.0.0.2", 443, scheme="https")],
                )

                def fake_run(cmd, **_kwargs):
                    Path(cmd[cmd.index("--out-cert") + 1]).write_text("certificate", encoding="utf-8")
                    Path(cmd[cmd.index("--out-key") + 1]).write_text("private-key", encoding="utf-8")
                    return ""

                with mock.patch.object(cli, "run", side_effect=fake_run):
                    cli.generate_internal_service_certs(cfg)

                cert_dir = cli.DATADIR / "service-certs" / "app"
                self.assertEqual((cert_dir / "cert.pem").read_text(), "certificate")
                self.assertEqual((cert_dir / "key.pem").read_text(), "private-key")
                self.assertEqual((cert_dir / "cert.pem").stat().st_mode & 0o777, 0o644)
                self.assertEqual((cert_dir / "key.pem").stat().st_mode & 0o777, 0o600)
                self.assertEqual(cert_dir.stat().st_mode & 0o777, 0o700)
                self.assertEqual(list(cert_dir.glob("*.tmp")), [])
        finally:
            cli.DATADIR = old_datadir
            cli.CADDY = old_caddy

    def test_intermediate_certificate_is_not_exported_as_root_ca(self):
        old_datadir = cli.DATADIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.DATADIR = Path(tmp)
                pki = cli.DATADIR / "pki" / "ca" / "internal"
                pki.mkdir(parents=True)
                (pki / "intermediate.crt").write_text(
                    "-----BEGIN CERTIFICATE-----\nintermediate\n-----END CERTIFICATE-----\n",
                    encoding="utf-8",
                )

                self.assertIsNone(cli.auto_export_internal_ca())
        finally:
            cli.DATADIR = old_datadir

    def test_existing_single_ca_format_repairs_missing_companion_file(self):
        old_datadir = cli.DATADIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cli.DATADIR = Path(tmp)
                export_dir = cli.DATADIR / "exported-certs"
                export_dir.mkdir(parents=True)
                pem = export_dir / "caddy-internal-ca.pem"
                pem.write_text("x" * 101, encoding="utf-8")

                result = cli.auto_export_internal_ca()

                self.assertIsNotNone(result)
                self.assertEqual((export_dir / "caddy-internal-ca.crt").read_text(), "x" * 101)
        finally:
            cli.DATADIR = old_datadir

    def test_export_caddy_internal_certs_reads_from_storage(self):
        old_datadir = cli.DATADIR
        old_caddy = cli.CADDY
        try:
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                cli.DATADIR = td
                cli.CADDY = td / "caddy-rebuild"
                cli.CADDY.write_text("dummy", encoding="utf-8")

                pki = td / "pki" / "ca" / "internal"
                pki.mkdir(parents=True, exist_ok=True)
                cert = pki / "root.pem"
                cert.write_text("-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n", encoding="utf-8")

                out = cli.export_caddy_internal_certs()
                pem = Path(out["ca_cert_pem"])
                crt = Path(out["ca_cert_crt"])

                self.assertTrue(pem.exists())
                self.assertTrue(crt.exists())
                self.assertIn("BEGIN CERTIFICATE", pem.read_text(encoding="utf-8"))
        finally:
            cli.DATADIR = old_datadir
            cli.CADDY = old_caddy


if __name__ == "__main__":
    unittest.main()
