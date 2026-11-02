from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from homelab_vision.lineage import LineageGraph, sha256_file, verify_fixture_manifest


class LineageTests(unittest.TestCase):
    def test_deletion_order_places_derivatives_first(self) -> None:
        graph = LineageGraph()
        graph.add_relation("source", "normalized")
        graph.add_relation("normalized", "embedding")
        graph.add_relation("normalized", "thumbnail")
        order = graph.deletion_order("source")
        self.assertLess(order.index("embedding"), order.index("normalized"))
        self.assertLess(order.index("thumbnail"), order.index("normalized"))
        self.assertEqual(order[-1], "source")

    def test_cycle_is_rejected(self) -> None:
        graph = LineageGraph()
        graph.add_relation("source", "derived")
        with self.assertRaises(ValueError):
            graph.add_relation("derived", "source")
        self.assertEqual(graph.deletion_order("source"), ("derived", "source"))

    def test_manifest_detects_changed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "sample.txt"
            fixture.write_text("before", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "fixtures": [
                            {
                                "id": "sample",
                                "path": "sample.txt",
                                "bytes": fixture.stat().st_size,
                                "sha256": sha256_file(fixture),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(verify_fixture_manifest(manifest), [])
            fixture.write_text("after", encoding="utf-8")
            self.assertTrue(verify_fixture_manifest(manifest))


if __name__ == "__main__":
    unittest.main()
