import unittest
from unittest.mock import patch

from pathforward.obs.appinsights import emit_custom_event


class AppInsightsEmitterTests(unittest.TestCase):
    def test_emit_custom_event_posts_to_connection_ingestion_endpoint(self):
        conn = ("InstrumentationKey=00000000-0000-0000-0000-000000000000;"
                "IngestionEndpoint=https://example.applicationinsights.azure.com/")

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("pathforward.obs.appinsights.request.urlopen", return_value=Response()) as open_:
            ok = emit_custom_event(
                conn,
                "pathforward.hosted.request",
                properties={"pf.status": "verified", "pf.credential_issued": False},
                measurements={"pf.attempts": 1},
            )

        self.assertTrue(ok)
        req = open_.call_args.args[0]
        self.assertEqual(req.full_url, "https://example.applicationinsights.azure.com/v2.1/track")
        body = req.data.decode("utf-8")
        self.assertIn("pathforward.hosted.request", body)
        self.assertIn('"pf.status": "verified"', body)
        self.assertIn('"pf.credential_issued": "False"', body)

    def test_emit_custom_event_fails_open_without_instrumentation_key(self):
        self.assertFalse(emit_custom_event("", "pathforward.hosted.request"))


if __name__ == "__main__":
    unittest.main()
