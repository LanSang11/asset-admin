import unittest
from datetime import datetime, timezone

from app.services.tls_cert import days_left, parse_openssl_date, parse_openssl_text


class TestTlsCertParse(unittest.TestCase):
    def test_parse_openssl_text_and_days(self):
        text = """
subject=CN = asset.example.com
issuer=C = US, O = Let's Encrypt, CN = R12
notBefore=Aug 17 01:00:00 2026 GMT
notAfter=Nov 15 01:00:00 2026 GMT
X509v3 Subject Alternative Name:
    DNS:asset.example.com
"""
        parsed = parse_openssl_text(text)
        self.assertEqual(parsed["subject"], "CN = asset.example.com")
        self.assertIn("Let's Encrypt", parsed["issuer"])
        self.assertEqual(parsed["san"], ["asset.example.com"])
        self.assertTrue(str(parsed["not_after"]).startswith("2026-11-15T01:00:00"))
        now = datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(days_left(parse_openssl_date("Nov 15 01:00:00 2026 GMT"), now), 90)

    def test_days_left_none_without_date(self):
        self.assertIsNone(days_left(None))
        self.assertIsNone(parse_openssl_date(""))
        self.assertIsNone(parse_openssl_date("not-a-date"))


if __name__ == "__main__":
    unittest.main()
