import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score import config  # noqa: E402


class FolderPicks(unittest.TestCase):
    def test_order(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"APPDATA": d, "DIPS_WOW": r"E:\env"}):
            self.assertEqual(config.paths().wow, Path(r"E:\env"))
            self.assertEqual(config.paths().logs, Path(r"E:\env\Logs"))
            (Path(d) / "dips-score").mkdir()
            (Path(d) / "dips-score" / "settings.json").write_text(
                json.dumps({"wow_folder": r"E:\picked", "logs_folder": r"F:\logs"}), encoding="utf-8")
            p = config.paths()
            self.assertEqual((p.wow, p.logs), (Path(r"E:\picked"), Path(r"F:\logs")))
            self.assertEqual(config.paths(r"E:\arg").wow, Path(r"E:\arg"))


class Version(unittest.TestCase):
    def test_read(self):
        import dips_score
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sys, "_MEIPASS", tmp, create=True):
            self.assertEqual(dips_score.version(), "")                  # a build without the file
            (Path(tmp) / "pyproject.toml").write_text('[project]\nversion = "1.2.3-a"\n', encoding="utf-8")
            self.assertEqual(dips_score.version(), "1.2.3-a")           # the installed app
        self.assertRegex(dips_score.version(), r"^\d+\.\d+\.\d+")      # from source


if __name__ == "__main__":
    unittest.main()
