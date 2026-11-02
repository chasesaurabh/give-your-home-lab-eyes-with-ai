from __future__ import annotations

import sqlite3
import unittest
from dataclasses import replace

from homelab_vision.inventory import (
    ConfirmationRequired,
    InventoryProposal,
    apply_confirmed_proposal,
    create_schema,
    rollback_event,
    item_revision,
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

    def test_event_failure_rolls_back_inventory_write(self):
        self.connection.execute("CREATE TRIGGER reject_event BEFORE INSERT ON change_events BEGIN SELECT RAISE(ABORT, 'injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            apply_confirmed_proposal(self.connection,self.proposal,confirmed=True,approved_by='reviewer',expected_revision=0)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM inventory').fetchone()[0],0)

    def test_stale_review_and_old_rollback_cannot_overwrite(self):
        apply_confirmed_proposal(self.connection,self.proposal,confirmed=True,approved_by='reviewer',expected_revision=0)
        first=item_revision(self.connection,self.proposal.item_id)
        with self.assertRaises(ConfirmationRequired):
            apply_confirmed_proposal(self.connection,replace(self.proposal,model='changed'),confirmed=True,approved_by='reviewer',expected_revision=0)
        apply_confirmed_proposal(self.connection,replace(self.proposal,model='changed'),confirmed=True,approved_by='reviewer',expected_revision=first)
        second=item_revision(self.connection,self.proposal.item_id)
        with self.assertRaises(ConfirmationRequired):
            rollback_event(self.connection,first,confirmed=True,approved_by='reviewer')
        rollback_event(self.connection,second,confirmed=True,approved_by='reviewer')
        self.assertEqual(self.connection.execute('SELECT model FROM inventory').fetchone()[0],self.proposal.model)
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM change_events').fetchone()[0],3)

    def test_rollback_create_retains_event_and_rejects_replay(self):
        apply_confirmed_proposal(self.connection,self.proposal,confirmed=True,approved_by='reviewer',expected_revision=0)
        first=item_revision(self.connection,self.proposal.item_id)
        rollback_event(self.connection,first,confirmed=True,approved_by='reviewer')
        self.assertEqual(self.connection.execute('SELECT COUNT(*) FROM inventory').fetchone()[0],0)
        with self.assertRaises(ConfirmationRequired):
            rollback_event(self.connection,first,confirmed=True,approved_by='reviewer')
        with self.assertRaises(ConfirmationRequired):
            apply_confirmed_proposal(self.connection,self.proposal,confirmed=True,approved_by='reviewer',expected_revision=0)


if __name__ == "__main__":
    unittest.main()
