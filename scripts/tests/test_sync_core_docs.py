from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from scripts import sync_core_docs


class SyncCoreDocsTests(unittest.TestCase):
    def test_resolver_accepts_only_allowlisted_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "README.md"
            allowed.write_text("core", encoding="utf-8")
            self.assertEqual(
                sync_core_docs.resolve_allowed_source(root, "README.md"),
                allowed.resolve(),
            )
            with self.assertRaises(ValueError):
                sync_core_docs.resolve_allowed_source(root, "secrets.txt")
            with self.assertRaises(ValueError):
                sync_core_docs.resolve_allowed_source(root, "../README.md")

    def test_agent_runtime_paths_are_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "never readable"):
                sync_core_docs.resolve_allowed_source(
                    Path(directory),
                    ".agent/sessions/private.jsonl",
                )

    def test_literal_exports_are_read_without_importing(self) -> None:
        source = b'__all__ = ["AgentEvent", "run_agent_events"]\n'
        self.assertEqual(
            sync_core_docs.python_all(source, "example.py"),
            ("AgentEvent", "run_agent_events"),
        )

    def test_human_notes_survive_regeneration(self) -> None:
        old = (
            f"prefix\n{sync_core_docs.HUMAN_START}\nReviewed locally.\n"
            f"{sync_core_docs.HUMAN_END}\n"
        )
        new = (
            f"new prefix\n{sync_core_docs.HUMAN_START}\nDefault.\n"
            f"{sync_core_docs.HUMAN_END}\n"
        )
        merged = sync_core_docs.preserve_human_notes(old, new)
        self.assertIn("Reviewed locally.", merged)
        self.assertNotIn("Default.", merged)


if __name__ == "__main__":
    unittest.main()
