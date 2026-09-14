"""Repeat the historical schema-capture failure site with caller attribution."""
import unittest

from loopback_transport_audit import LoopbackTransportAudit
import test_schema_capture as schema_capture


class SchemaCaptureRouteAuditTests(unittest.TestCase):
    def setUp(self):
        self.case = schema_capture.SchemaCaptureTests(
            methodName="test_historical_report_requires_all_contract_fields_and_valid_shape"
        )
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.audit = LoopbackTransportAudit(
            host="127.0.0.1",
            port=self.case.http.server_port,
            max_calls=16,
            max_frames=16,
        )
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def test_historical_report_replay_has_one_attributed_capture_connection(self):
        try:
            self.case.test_historical_report_requires_all_contract_fields_and_valid_shape()
        except AssertionError as error:
            self.fail(f"{error}\nloopback audit: {self.audit.describe(self.case.routes)}")

        diagnostic = self.audit.describe(self.case.routes)
        self.assertEqual(self.case.routes, [("GET", "/object_info")], diagnostic)
        snapshot = self.audit.snapshot()
        self.assertEqual(snapshot["observed"], 1, diagnostic)
        self.assertEqual(len(snapshot["retained"]), 1, diagnostic)
        self.assertFalse(snapshot["truncated"], diagnostic)
        functions = [frame["function"] for frame in snapshot["retained"][0]["stack"]]
        self.assertTrue(
            any(name in functions for name in ("capture", "cli", "main")),
            diagnostic,
        )


if __name__ == "__main__":
    unittest.main()
