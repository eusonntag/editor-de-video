"""Desfoque de áreas da tela (dados pessoais, e-mails, números), aplicado no quadro de origem.

As regiões ficam em <trabalho>/desfoque.json, na linha do tempo do vídeo cortado:
  {"regioes": [{"inicio": 12.0, "fim": 18.5, "x": 0.12, "y": 0.40, "w": 0.30, "h": 0.06,
                "rotulo": "e-mail", "forca": 1.0, "ativo": true}]}
x, y, w, h são frações (0 a 1) do quadro do cortado.mp4, então valem em qualquer formato e resolução.
O desfoque é aplicado ANTES do zoom e do recorte: a área continua coberta se a imagem aproximar ou o
vertical recortar. Usado por layout.py (todos os formatos e o rascunho).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def ler(trab: Path) -> list[dict]:
    arq = trab / "desfoque.json"
    if not arq.exists():
        return []
    try:
        return json.loads(arq.read_text(encoding="utf-8")).get("regioes", [])
    except (json.JSONDecodeError, OSError):
        return []


class Desfoque:
    """Aplica as regiões ativas num quadro BGR (numpy), conforme o tempo (s) do quadro."""

    MARGEM = 0.004  # folga em volta da área, como fração do quadro

    def __init__(self, regioes: list[dict]):
        self.reg = []
        for r in regioes or []:
            if not r.get("ativo", True):
                continue
            try:
                self.reg.append({k: float(r[k]) for k in ("inicio", "fim", "x", "y", "w", "h")}
                                | {"forca": float(r.get("forca", 1.0))})
            except (KeyError, TypeError, ValueError):
                continue

    def __bool__(self) -> bool:
        return bool(self.reg)

    def __len__(self) -> int:
        return len(self.reg)

    def aplicar(self, quadro: np.ndarray, t: float) -> np.ndarray:
        import cv2

        h, w = quadro.shape[:2]
        saida = quadro
        for r in self.reg:
            if not (r["inicio"] <= t < r["fim"]):
                continue
            if saida is quadro:
                saida = quadro.copy()  # o quadro decodificado é somente leitura
            x0 = max(0, int((r["x"] - self.MARGEM) * w))
            y0 = max(0, int((r["y"] - self.MARGEM * w / h) * h))
            x1 = min(w, int(np.ceil((r["x"] + r["w"] + self.MARGEM) * w)))
            y1 = min(h, int(np.ceil((r["y"] + r["h"] + self.MARGEM * w / h) * h)))
            if x1 - x0 < 2 or y1 - y0 < 2:
                continue
            roi = saida[y0:y1, x0:x1]
            # sigma proporcional ao lado menor: texto de qualquer tamanho fica ilegível
            sigma = max(8.0, 0.3 * min(x1 - x0, y1 - y0)) * max(0.3, r["forca"])
            # desfoque forte numa versão reduzida da área (muito mais rápido, resultado igual a olho nu)
            f = max(1.0, sigma / 4.0)
            pw, ph = max(2, int(round((x1 - x0) / f))), max(2, int(round((y1 - y0) / f)))
            pequeno = cv2.resize(roi, (pw, ph), interpolation=cv2.INTER_AREA)
            pequeno = cv2.GaussianBlur(pequeno, (0, 0), sigma / f, borderType=cv2.BORDER_REPLICATE)
            saida[y0:y1, x0:x1] = cv2.resize(pequeno, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
        return saida
