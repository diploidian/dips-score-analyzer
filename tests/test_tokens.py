import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dips_score.ui import tokens  # noqa: E402


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

    def test_normalize(self):
        self.assertEqual(tokens.normalize("wow", None), ("timeless", "auto"))
        self.assertEqual(tokens.normalize("classic", "night"), ("timeless", "night"))
        self.assertEqual(tokens.normalize("classical", "bogus"), ("classical", "auto"))

    def test_resolve(self):
        self.assertEqual(tokens.resolve("auto", True), "night")
        self.assertEqual(tokens.resolve("auto", False), "day")
        self.assertEqual(tokens.resolve("day", True), "day")

    def test_ink_for(self):
        self.assertEqual(tokens.ink_for("Cooldowns"), "m-cd")
        self.assertEqual(tokens.ink_for("Something new"), "m-act")


if __name__ == "__main__":
    unittest.main()
