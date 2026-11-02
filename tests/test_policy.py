from __future__ import annotations

import unittest

from homelab_vision.contracts import ActionRequest
from homelab_vision.policy import ActionPolicy, EgressPolicy, PolicyViolation


class PolicyTests(unittest.TestCase):
    def test_remote_media_is_denied_by_default(self) -> None:
        with self.assertRaises(PolicyViolation):
            EgressPolicy().validate_media_url("https://media.invalid/image.png")

    def test_only_exact_https_host_is_allowed(self) -> None:
        policy = EgressPolicy(True, frozenset({"fixtures.example.org"}))
        policy.validate_media_url("https://fixtures.example.org/image.png")
        for url in (
            "http://fixtures.example.org/image.png",
            "https://other.example.org/image.png",
            "https://fixtures.example.org.evil.test/image.png",
        ):
            with self.assertRaises(PolicyViolation):
                policy.validate_media_url(url)

    def test_action_requires_exact_allowlist_match(self) -> None:
        policy = ActionPolicy({"status": frozenset({"read"})})
        policy.authorize(ActionRequest("status", "read"))
        with self.assertRaises(PolicyViolation):
            policy.authorize(ActionRequest("status", "restart"))


if __name__ == "__main__":
    unittest.main()
