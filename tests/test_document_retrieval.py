from __future__ import annotations

import unittest
from pathlib import Path

from homelab_vision.document import ingest_markdown
from homelab_vision.retrieval import LexicalIndex


ROOT = Path(__file__).resolve().parents[1]


class DocumentRetrievalTests(unittest.TestCase):
    def test_ingestion_preserves_line_provenance(self) -> None:
        chunks = ingest_markdown(
            ROOT / "fixtures" / "source" / "maintenance-sheet.md",
            "doc-maintenance-sheet-v1",
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.source.locator.startswith("lines:") for chunk in chunks))
        self.assertEqual(len(chunks[0].source.sha256), 64)

    def test_instruction_like_fixture_is_flagged_but_preserved(self) -> None:
        chunks = ingest_markdown(
            ROOT / "fixtures" / "source" / "untrusted-note.md",
            "doc-untrusted-note-v1",
        )
        flagged = [chunk for chunk in chunks if chunk.instruction_like]
        self.assertEqual(len(flagged), 1)
        self.assertIn("Ignore prior instructions", flagged[0].text)

    def test_lexical_baseline_returns_inspectable_source(self) -> None:
        maintenance = ingest_markdown(
            ROOT / "fixtures" / "source" / "maintenance-sheet.md",
            "doc-maintenance-sheet-v1",
        )
        untrusted = ingest_markdown(
            ROOT / "fixtures" / "source" / "untrusted-note.md",
            "doc-untrusted-note-v1",
        )
        hits = LexicalIndex(maintenance + untrusted).search("storage status LAB-GW-01", top_k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk.source.fixture_id, "doc-maintenance-sheet-v1")
        self.assertIn("lines:", hits[0].chunk.source.locator)

    def test_empty_query_has_no_results(self) -> None:
        chunks = ingest_markdown(
            ROOT / "fixtures" / "source" / "maintenance-sheet.md",
            "doc-maintenance-sheet-v1",
        )
        self.assertEqual(LexicalIndex(chunks).search("---"), ())


if __name__ == "__main__":
    unittest.main()
