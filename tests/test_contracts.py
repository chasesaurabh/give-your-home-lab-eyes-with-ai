from __future__ import annotations

import unittest

from homelab_vision.contracts import (
    ActionRequest,
    Observation,
    OutcomeStatus,
    ProcessingResult,
    SourceReference,
)


GOOD_HASH = "a" * 64


class ContractTests(unittest.TestCase):
    def test_source_reference_requires_sha256(self) -> None:
        with self.assertRaises(ValueError):
            SourceReference("fixture", "not-a-hash", "page:1", "text/markdown")

    def test_observation_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            Observation("storage_percent", 72, ())

    def test_failed_result_requires_error_code(self) -> None:
        with self.assertRaises(ValueError):
            ProcessingResult(status=OutcomeStatus.FAILED)

    def test_action_request_does_not_execute(self) -> None:
        request = ActionRequest("status", "read", {"asset": "LAB-GW-01"})
        result = ProcessingResult(
            status=OutcomeStatus.PARTIAL,
            requested_actions=(request,),
            warnings=("authorization remains pending",),
        )
        self.assertEqual(result.requested_actions[0].operation, "read")


if __name__ == "__main__":
    unittest.main()
