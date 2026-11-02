from __future__ import annotations

import sqlite3
import unittest
from dataclasses import replace

from homelab_vision.inventory import (
    ConfirmationRequired,
    InventoryProposal,
    apply_confirmed_proposal,
    create_schema,
)


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        create_schema(self.connection)
        self.proposal = InventoryProposal(
            item_id="lab-switch-01",
            equipment_class="switch",
            manufacturer="Example Networks",
            model="XN-2400",
            serial="XN2400-0001",
            source_digest="a" * 64,
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_mutation_requires_confirmation(self) -> None:
        with self.assertRaises(ConfirmationRequired):
            apply_confirmed_proposal(
                self.connection,
                self.proposal,
                confirmed=False,
                approved_by="reviewer",
            )
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0], 0)

    def test_uncertainty_blocks_mutation(self) -> None:
        uncertain = replace(self.proposal, uncertainty=("serial character unclear",))
        with self.assertRaises(ConfirmationRequired):
            apply_confirmed_proposal(
                self.connection,
                uncertain,
                confirmed=True,
                approved_by="reviewer",
            )

    def test_confirmed_mutation_and_event_commit_together(self) -> None:
        apply_confirmed_proposal(
            self.connection,
            self.proposal,
            confirmed=True,
            approved_by="reviewer",
        )
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0], 1)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM change_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
