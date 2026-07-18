import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import certify_reverse.cli as cli


class CliExportTests(unittest.TestCase):
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
