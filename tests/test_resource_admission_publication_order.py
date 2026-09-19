"""Reservation publication must never outlive a failed receipt operation."""
from __future__ import annotations

import copy
import unittest

from test_resource_admission import GRAPH, Studio, admission, observation, profile_for


class ResourceAdmissionPublicationOrderTests(unittest.TestCase):
    @staticmethod
    def _inactive_receipt(owner_id):
        value = {
            "schema": admission.SCHEMA,
            "owner_id": owner_id,
            "kind": "generation",
            "recorded_at": 1.0,
            "identity_sha256": "a" * 64,
            "decision": "unknown",
            "state": "refused",
            "reservation": None,
        }
        value["receipt_sha256"] = admission._digest(value)
        return value

    def test_oversized_receipt_refuses_before_new_reservation_is_published(self):
        studio = Studio()
        profile, identity = profile_for(studio)
        oversized = observation()
        oversized["runtime"]["diagnostic"] = "x" * admission.MAX_DOCUMENT_BYTES
        ledger = admission.ReservationLedger()

        with self.assertRaisesRegex(ValueError, "document exceeds"):
            ledger.admit("job", identity, profile, oversized)

        self.assertEqual(ledger.snapshot()["owners"], [])
        self.assertEqual(
            ledger.snapshot()["totals"],
            {dimension: 0 for dimension in admission.DIMENSIONS},
        )

    def test_rejected_receipt_publisher_prevents_reservation_publication(self):
        studio = Studio()
        profile, identity = profile_for(studio)
        ledger = admission.ReservationLedger()
        published = []

        def reject(receipt):
            published.append(receipt)
            raise RuntimeError("receipt store unavailable")

        with self.assertRaisesRegex(RuntimeError, "receipt store unavailable"):
            ledger.admit(
                "job",
                identity,
                profile,
                observation(),
                publish=reject,
            )

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["state"], "reserved")
        self.assertEqual(ledger.snapshot()["owners"], [])

    def test_full_history_refuses_before_new_reservation_is_published(self):
        studio = Studio()
        profile_for(studio)
        owner_id = "job"
        retained = self._inactive_receipt(owner_id)
        job = {
            "id": owner_id,
            "status": "running",
            "submissions": [],
            "resource_admission": [
                copy.deepcopy(retained) for _ in range(admission.MAX_RECEIPTS)
            ],
        }
        studio.jobs = {owner_id: job}
        controller = admission.AdmissionController(
            studio,
            observer=lambda _: observation(),
        )

        with self.assertRaisesRegex(ValueError, "retention is full"):
            controller.admit(job, {"id": "demo"}, GRAPH)

        self.assertEqual(controller.ledger.snapshot()["owners"], [])
        self.assertEqual(len(job["resource_admission"]), admission.MAX_RECEIPTS)


if __name__ == "__main__":
    unittest.main()
