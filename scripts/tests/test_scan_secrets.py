import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scan_secrets.py"
SPEC = importlib.util.spec_from_file_location("presenton_secret_scan", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
SECRET_SCAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SECRET_SCAN)


class SecretScannerTests(unittest.TestCase):
    def test_detects_a_production_shaped_value_without_reporting_it(self):
        synthetic_secret = "sk-" + "presenton-" + ("A" * 32)

        findings = list(
            SECRET_SCAN._findings(
                "synthetic.txt",
                f'Authorization: Bearer {synthetic_secret}',
            )
        )

        self.assertTrue(findings)
        self.assertTrue(all(len(item) == 2 for item in findings))
        self.assertNotIn(synthetic_secret, repr(findings))

    def test_allows_an_explicitly_invalid_test_fixture(self):
        fake_secret = "sk-" + "presenton-clearly-invalid-test-token"

        findings = list(
            SECRET_SCAN._findings("fixture.txt", f'token = "{fake_secret}"')
        )

        self.assertEqual(findings, [])

    def test_rejects_generated_browser_artifacts_even_when_binary(self):
        self.assertTrue(
            SECRET_SCAN._is_forbidden_artifact(
                "servers/nextjs/.playwright-cli/session.png"
            )
        )
        self.assertTrue(
            SECRET_SCAN._is_forbidden_artifact("test-results/browser.trace.zip")
        )
        self.assertFalse(
            SECRET_SCAN._is_forbidden_artifact("readme_assets/product-demo.png")
        )

    def test_redacts_a_credential_if_it_appears_in_a_filename(self):
        synthetic_secret = "sk-" + "presenton-" + ("B" * 32)

        redacted = SECRET_SCAN._redact(f"artifacts/{synthetic_secret}.txt")

        self.assertNotIn(synthetic_secret, redacted)
        self.assertIn("[REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
