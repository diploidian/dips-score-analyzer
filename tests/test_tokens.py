import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dips_score.config import Paths  # noqa: E402
from dips_score.ui import settings_store, tokens  # noqa: E402


def contrast(a: str, b: str) -> float:
    """WCAG contrast of two #rrggbb colours"""
    def lum(h):
        def ch(v):
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class TokensTest(unittest.TestCase):
    def test_tokens_match_css(self):
        css = (ROOT / "docs/design/mockups/assets/theme.css").read_text(encoding="utf-8")
        blocks = re.findall(r'html\[data-theme="(\w+)"\]\[data-mode="(\w+)"\]\s*\{(.*?)\}', css, re.S)
        self.assertEqual(len(blocks), 4)
        for theme, mode, body in blocks:
            parsed = {k: v.strip().lower() for k, v in re.findall(r"--([\w-]+):\s*([^;]+);", body)}
            self.assertEqual(len(parsed), 36)
            got = {k: v.lower() for k, v in tokens.TOKENS[(theme, mode)].items()}
            self.assertEqual(got, parsed, (theme, mode))

    def test_text_reads_on_panel(self):
        """tx on panel (the timeline's crosshair readout, and much of the kit) reaches 4.5:1 in all four looks"""
        self.assertEqual(len(tokens.TOKENS), 4)
        for look, t in tokens.TOKENS.items():
            self.assertGreaterEqual(contrast(t["tx"], t["panel"]), 4.5, look)

    def test_rail_text_reads_on_rail(self):
        """the rail's run tree and fight list: rail-tx (names) and rail-mu (muted line, tags) reach 4.5:1 on the rail
        and on the picked row (rail-on) in all four looks"""
        for look, t in tokens.TOKENS.items():
            for ink in ("rail-tx", "rail-mu"):
                for bg in ("rail", "rail-on"):
                    self.assertGreaterEqual(contrast(t[ink], t[bg]), 4.5, (look, ink, bg))

    def test_normalize(self):
        self.assertEqual(tokens.normalize("wow", None), ("timeless", "auto"))
        self.assertEqual(tokens.normalize("classic", "night"), ("timeless", "night"))
        self.assertEqual(tokens.normalize("classical", "bogus"), ("classical", "auto"))

    def test_normalize_non_strings(self):
        self.assertEqual(tokens.normalize(["x"], {"a": 1}), ("timeless", "auto"))
        self.assertEqual(tokens.normalize(5, None), ("timeless", "auto"))

    def test_resolve(self):
        self.assertEqual(tokens.resolve("auto", True), "night")
        self.assertEqual(tokens.resolve("auto", False), "day")
        self.assertEqual(tokens.resolve("day", True), "day")

    def test_ink_for(self):
        self.assertEqual(tokens.ink_for("Cooldowns"), "m-cd")
        self.assertEqual(tokens.ink_for("Something new"), "m-act")

    def test_settings_legacy_theme(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.get("APPDATA")
            os.environ["APPDATA"] = d
            try:
                paths = Paths(Path(d))
                (paths.data_dir).mkdir()
                (paths.data_dir / "settings.json").write_text('{"theme": "wow"}', encoding="utf-8")
                got = settings_store.load(paths)
            finally:
                if old is None:
                    del os.environ["APPDATA"]
                else:
                    os.environ["APPDATA"] = old
        self.assertEqual((got["theme"], got["mode"]), ("timeless", "auto"))


if __name__ == "__main__":
    unittest.main()
