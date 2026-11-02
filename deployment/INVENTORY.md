# Review a label before changing inventory

This is a single-user CLI workflow. The model has no database API. Review digests and item revisions prevent accidental stale commits through this interface; they are not authentication against a user who can alter local files or the database directly.

With the model running as `vision-2b`, from the repository root:

```bash
homelab-vision analyze fixtures/source/equipment-label.png --task label --model vision-2b --output runs/inventory-label
homelab-vision inventory --database runs/inventory.sqlite init
homelab-vision inventory --database runs/inventory.sqlite prepare runs/inventory-label --output runs/inventory-review --item-id lab-label-01 --class network-appliance
homelab-vision inventory --database runs/inventory.sqlite inspect runs/inventory-review
```

The original fictional label says `LAB-135`, model `Juniper-11`, 24 ports and `12 V DC`. It is not a real product specification. The draft copies only the model name into the small inventory schema. The class and local item ID come from you; manufacturer and serial remain null. Other observed fields stay in `observation.json`.

Open `evidence.png` and compare every field. Correct only `fields` in `review.json` if needed, leaving unknowns null. Do not rewrite `observation.json` to conceal a model error. Inspect again after any edit. Possible exact serial/model matches are suggestions, never automatic merges.

Replace `REVIEW_SHA256` with the digest printed by the latest inspection:

```bash
homelab-vision inventory --database runs/inventory.sqlite commit runs/inventory-review --confirm-digest REVIEW_SHA256 --reviewer local-reviewer
homelab-vision inventory --database runs/inventory.sqlite export
homelab-vision inventory --database runs/inventory.sqlite backup --output runs/inventory-snapshot.sqlite
```

A commit verifies evidence and the exact review file, then checks the current item revision inside an immediate SQLite transaction. The accepted row and history event commit together. Repeating the same commit is rejected as stale. Prepare a new review if the target changed; do not edit the revision to bypass review.

The commit returns an event ID. Only the latest event for an item can be rolled back. Use the actual ID, not an assumed `1` on an existing database:

```bash
homelab-vision inventory --database runs/inventory.sqlite rollback --event-id 1 --reviewer local-reviewer --confirm
homelab-vision inventory --database runs/inventory.sqlite export
homelab-vision inventory --database runs/inventory-snapshot.sqlite export
```

Rollback restores the earlier row (or removes a newly created row) and appends a new event. It does not erase history or remove evidence files. Backups refuse an existing destination, use SQLite's backup API and run an integrity check. Copy evidence directories separately. Same-disk backups do not establish disaster recovery.

The measured integration reused an actual 2B model extraction and passed ten CLI lifecycle checks: creation, preparation, commit, replay rejection, export, backup, rollback, empty-current/history-preserved export, old-rollback rejection and reopening the snapshot. Reviewer/class inputs were declared fictional test inputs. Tests additionally inject event-write failure, stale updates, changed review bytes and tampered evidence. No model accuracy claim follows from those database tests.

No web UI, remote authentication, fuzzy matching, shared-source deletion or automatic retention is implemented. Export includes accepted data and history; protect it accordingly. To remove a demonstration, close its database and deliberately remove its database, snapshots, review and analysis directories. Removing a current row alone does not remove earlier values from history or backups.
