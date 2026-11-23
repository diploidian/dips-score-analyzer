"""Runs and fights you deleted (removed.py): kept in removed.json, skipped on load."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import removed  # noqa: E402


class Removed(unittest.TestCase):
    def test_add_reload_and_a_broken_file(self):
        self.addCleanup(removed.IDS.clear)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dips-score" / "removed.json"     # the folder isn't there yet
            removed.load(path)
            self.assertEqual(removed.IDS, set())
            removed.add(path, ["1763-Nikana", "20261118233849824000"])
            removed.add(path, ["1764-Nikana"])
            removed.load(path)                                   # from disk, as at the next start
            self.assertEqual(removed.IDS, {"1763-Nikana", "1764-Nikana", "20261118233849824000"})
            path.write_text("not json", encoding="utf-8")
            removed.load(path)                                   # a broken file: nothing deleted, no crash
            self.assertEqual(removed.IDS, set())


if __name__ == "__main__":
    unittest.main()
