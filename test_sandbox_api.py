import io
import unittest
import urllib.error
from unittest.mock import Mock
from lab.sandbox_api import APIError, NoRedirect, SandboxHTTP, TastytradeSandbox, AlpacaPaper, OandaPractice


class SandboxBoundaryTests(unittest.TestCase):
    def test_production_credentials_rejected_before_network(self):
        for cls in (TastytradeSandbox, AlpacaPaper, OandaPractice):
            with self.assertRaises(ValueError):
                cls({"environment": "live"})

    def test_paths_cannot_change_host(self):
        client = SandboxHTTP("tastytrade")
        client.opener = Mock()
        for path in ("https://api.tastyworks.com/orders", "//evil.example/orders", "orders"):
            with self.assertRaises(ValueError):
                client.request("POST", path, {})
        client.opener.open.assert_not_called()

    def test_market_data_host_rejects_mutations(self):
        client = SandboxHTTP("alpaca_data")
        client.opener = Mock()
        with self.assertRaises(ValueError):
            client.request("POST", "/v2/orders", {})
        client.opener.open.assert_not_called()

    def test_redirect_does_not_forward_credentials(self):
        with self.assertRaises(APIError):
            NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://other.example")

    def test_failed_order_post_is_never_retried_and_body_is_redacted(self):
        client = SandboxHTTP("tastytrade")
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError(
            "https://api.cert.tastyworks.com/test", 503, "private account info", {}, io.BytesIO(b"SECRET"))
        with self.assertRaisesRegex(APIError, "HTTP 503") as ctx:
            client.request("POST", "/orders", {})
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertEqual(client.opener.open.call_count, 1)


if __name__ == "__main__":
    unittest.main()
