"""Double-click to open projectArthas (no terminal window).

From any folder, in any shell:
    python "D:\\projects\\projectArthas\\projectArthas.pyw" report
    python "D:\\projects\\projectArthas\\projectArthas.pyw" runs
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dips_score.__main__ import main  # noqa: E402

sys.exit(main(sys.argv[1:] or ["gui"]))
