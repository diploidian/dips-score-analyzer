"""Your names for runs and fights (names.py): kept in names.json, shown beside the original."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import names  # noqa: E402


class Names(unittest.TestCase):
    def test_rename_clear_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dips-score" / "names.json"      # the folder isn't there yet
            names.load(path)
            self.assertEqual(names.titled("1763-Nikana", "Scarlet Monastery"), "Scarlet Monastery")
            names.rename(path, "1763-Nikana", "  guild run with Anna ")
            names.rename(path, "20261118233849824000", "the oracle")
            self.assertEqual(names.titled("1763-Nikana", "Scarlet Monastery"),
                             "Scarlet Monastery — guild run with Anna")
            names.load(path)                                    # from disk, as at the next start
            self.assertEqual((names.get("1763-Nikana"), names.get("20261118233849824000")),
                             ("guild run with Anna", "the oracle"))
            names.rename(path, "1763-Nikana", "")               # empty: back to the original
            names.load(path)
            self.assertEqual((names.get("1763-Nikana"), names.titled("1763-Nikana", "SM")), ("", "SM"))
            path.write_text("not json", encoding="utf-8")
            names.load(path)                                    # a broken file: no names, no crash
            self.assertEqual(names.NAMES, {})


if __name__ == "__main__":
    unittest.main()
