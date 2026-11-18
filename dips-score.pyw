"""Double-click to open dips score (no terminal window).

From any folder, in any shell:
    python "D:\\projects\\dips-score-analyzer\\dips-score.pyw" report
    python "D:\\projects\\dips-score-analyzer\\dips-score.pyw" runs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dips_score.__main__ import main  # noqa: E402

sys.exit(main(sys.argv[1:] or ["gui"]))
