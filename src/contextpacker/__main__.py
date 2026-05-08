"""Entry point for ``python -m contextpacker`` — launches the Streamlit GUI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    gui = Path(__file__).parent / "gui.py"
    sys.exit(subprocess.call(["streamlit", "run", str(gui)] + sys.argv[1:]))


if __name__ == "__main__":
    main()
