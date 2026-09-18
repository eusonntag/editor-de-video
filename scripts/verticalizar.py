"""Atalho mantido por compatibilidade: a versão vertical agora é feita pelo layout.py.

  python -X utf8 scripts/verticalizar.py <trabalho> [--sem-zoom]
equivale a
  python -X utf8 scripts/layout.py <trabalho> vertical [--sem-zoom]

Saída: <trabalho>/vertical/base.mp4 + layout.json (rosto no quadro vertical e posição da legenda).
A detecção de rosto fica em scripts/rosto.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    layout = Path(__file__).resolve().parent / "layout.py"
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", str(layout), args[0], "vertical", *args[1:]]))
