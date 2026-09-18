"""Prepara um projeto HyperFrames "à mão" (tipo personalizado ou composição livre) para um formato
já montado pelo layout. Para os cards normais use scripts/motion.py, que faz isso sozinho.

Cria em <trabalho>/motion/<formato>/manual/public/:
  input-video.mp4   -> base.mp4 do formato (já tem keyframe a cada segundo)
  fonts/            -> todas as fontes TTF de assets/fontes
  vendor/gsap.min.js
  (e em manual/) metadata.json com largura / altura / fps / duração e transcript.json

Depois: escrever public/index.html seguindo o contrato do HyperFrames e renderizar com
  editor.py motion ... (ou node_modules/.bin/hyperframes render <public> -o <trabalho>/<formato>/animado.mp4)

Uso:
  python -X utf8 scripts/preparar_hyperframes.py <trabalho> [--formato horizontal]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import FONTES, RAIZ, info_video  # noqa: E402

GSAP = RAIZ / "node_modules" / "gsap" / "dist" / "gsap.min.js"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trabalho", type=Path)
    ap.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    a = ap.parse_args()

    trab = a.trabalho.resolve()
    base = trab / a.formato / "base.mp4"
    palavras = trab / "palavras.json"
    if not base.exists():
        raise SystemExit(f"falta {base}: rode o layout ({a.formato}) antes")
    if not palavras.exists():
        raise SystemExit(f"falta {palavras}: rode o corte antes")

    manual = trab / "motion" / a.formato / "manual"
    pub = manual / "public"
    for d in ("fonts", "vendor", "cards"):
        (pub / d).mkdir(parents=True, exist_ok=True)
    for f in FONTES.glob("*.ttf"):
        shutil.copy2(f, pub / "fonts" / f.name)
    shutil.copy2(GSAP, pub / "vendor" / "gsap.min.js")
    destino = pub / "input-video.mp4"
    destino.unlink(missing_ok=True)
    try:
        os.link(base, destino)
    except OSError:
        shutil.copy2(base, destino)

    info = info_video(base)
    meta = {"width": info["largura"], "height": info["altura"], "fps": info["fps_int"], "duration": info["duracao"]}
    (manual / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    shutil.copy2(palavras, manual / "transcript.json")
    print(f"pronto: {pub}")
    print(f"  {meta['width']}x{meta['height']} @ {meta['fps']}fps, {meta['duration']:.2f}s")


if __name__ == "__main__":
    main()
