"""Analyses kept on disk (store.py): read back only when made from the same key by the same code."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import store  # noqa: E402


class Store(unittest.TestCase):
    def test_save_load_and_what_misses(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cache" / "analysis"          # the folder isn't there yet
            key = ("1763-Nikana", 48, (("WoWCombatLog.txt", "settled"),), 0)
            store.save(folder, "1763-Nikana", key, SimpleNamespace(score=87, rows=[1, 2]))
            self.assertEqual(store.load(folder, "1763-Nikana", key), SimpleNamespace(score=87, rows=[1, 2]))
            self.assertIsNone(store.load(folder, "1763-Nikana", key[:3] + (1.5,)))     # role picks changed
            self.assertIsNone(store.load(folder, "1764-Nikana", key))                  # never saved
            with mock.patch.object(store, "stamp", return_value=0.0):                 # newer code
                self.assertIsNone(store.load(folder, "1763-Nikana", key))
            (folder / "1763-Nikana.pkl").write_bytes(b"not a pickle")
            self.assertIsNone(store.load(folder, "1763-Nikana", key))                  # broken: no crash
            store.save(folder, "17:63/x", key, 1)                                      # an odd id still saves
            self.assertEqual(store.load(folder, "17:63/x", key), 1)
            self.assertEqual(list(folder.glob("*.tmp")), [])

    def test_prune_keeps_the_named_runs_and_other_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for rid in ("1763-Nikana", "1764-Nikana", "1765-Bao"):
                store.save(folder, rid, (rid,), 1)
            store.prune(folder, ["1764-Nikana"])
            self.assertEqual(sorted(f.name for f in folder.iterdir()), ["1764-Nikana.pkl", "1765-Bao.pkl"])
            store.prune(folder, [])                                  # no runs read (no game folder): all stay
            self.assertEqual(len(list(folder.iterdir())), 2)

    def test_clear_drops_the_runs_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            store.clear(folder / "never made")
            for rid in ("1763-Nikana", "1765-Bao"):
                store.save(folder, rid, (rid,), 1)
            (folder / "other.txt").write_text("not the store's", encoding="utf-8")
            store.clear(folder)
            self.assertEqual([f.name for f in folder.iterdir()], ["other.txt"])


if __name__ == "__main__":
    unittest.main()
