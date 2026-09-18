"""Detecção e rastreamento do rosto (OpenCV Haar, sem internet).

Usado pelo layout (recorte vertical/react e centro dos zooms) e pelo motion (onde os cards
não podem ficar). O resultado fica em cache em <trabalho>/rosto.json.

  rastrear(video)            -> {"amostras": [[t, cx, cy, w, h], ...], "largura", "altura", ...}
  Trilha(dados).centro(t)    -> (cx, cy) suavizado
  Trilha(dados).tamanho()    -> (w, h) mediano do rosto

Uso direto:
  python -X utf8 scripts/rosto.py video.mp4 [-o rosto.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def detectar_rostos(video: Path, intervalo_s: float = 0.2) -> tuple[list[tuple[float, float, float, float, float]], dict]:
    import cv2

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    passo = max(1, int(round(fps * intervalo_s)))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    res = []
    i = 0
    while i < n:
        # ler em sequência é bem mais rápido que buscar quadro a quadro
        ok = cap.grab()
        if not ok:
            break
        if i % passo == 0:
            ok, f = cap.retrieve()
            if ok:
                esc = 640 / f.shape[1]
                g = cv2.cvtColor(cv2.resize(f, None, fx=esc, fy=esc), cv2.COLOR_BGR2GRAY)
                g = cv2.equalizeHist(g)
                faces = casc.detectMultiScale(g, 1.1, 6, minSize=(int(40 * 640 / 960), int(40 * 640 / 960)))
                if len(faces):
                    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                    res.append((i / fps, (x + w / 2) / esc, (y + h / 2) / esc, w / esc, h / esc))
        i += 1
    cap.release()
    return res, {"largura": W, "altura": H, "fps": fps, "duracao": n / fps if fps else 0}


def _sem_outliers(amostras: list) -> list:
    if len(amostras) < 5:
        return amostras
    a = np.array(amostras)
    med = np.median(a[:, 1:], axis=0)
    mad = np.median(np.abs(a[:, 1:] - med), axis=0) + 1e-6
    ok = np.all(np.abs(a[:, 1:] - med) <= 6 * mad + 0.08 * med[3], axis=1)
    return [amostras[i] for i in range(len(amostras)) if ok[i]]


def rastrear(video: Path, cache: Path | None = None) -> dict:
    video = Path(video)
    if cache and cache.exists():
        dados = json.loads(cache.read_text(encoding="utf-8"))
        if dados.get("origem_mtime") == int(video.stat().st_mtime) and dados.get("origem") == video.name:
            return dados
    amostras, meta = detectar_rostos(video)
    amostras = _sem_outliers(amostras)
    dados = {**meta, "origem": video.name, "origem_mtime": int(video.stat().st_mtime),
             "amostras": [[round(v, 2) for v in a] for a in amostras]}
    if amostras:
        a = np.array(amostras)
        dados["mediana"] = {"cx": round(float(np.median(a[:, 1]))), "cy": round(float(np.median(a[:, 2]))),
                            "w": round(float(np.median(a[:, 3]))), "h": round(float(np.median(a[:, 4])))}
        dados["extremos"] = {"x_min": round(float((a[:, 1] - a[:, 3] / 2).min())),
                             "x_max": round(float((a[:, 1] + a[:, 3] / 2).max())),
                             "y_min": round(float((a[:, 2] - a[:, 4] / 2).min())),
                             "y_max": round(float((a[:, 2] + a[:, 4] / 2).max()))}
    else:
        # sem rosto (tela, produto, desenho): assume pessoa centralizada no terço de cima
        W, H = meta["largura"], meta["altura"]
        dados["mediana"] = {"cx": W // 2, "cy": int(H * 0.4), "w": int(min(W, H) * 0.25), "h": int(min(W, H) * 0.25)}
        dados["extremos"] = None
        dados["sem_rosto"] = True
    if cache:
        cache.write_text(json.dumps(dados, indent=1), encoding="utf-8")
    return dados


def quadro_bom(video: Path, candidatos: list[float]) -> float:
    """Entre os instantes candidatos, o primeiro com rosto e os dois olhos abertos (para prévias
    e galerias não mostrarem a pessoa piscando). Sem nenhum bom, devolve o primeiro."""
    import cv2

    casc_r = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    casc_o = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
    cap = cv2.VideoCapture(str(video))
    try:
        for t in candidatos:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, f = cap.read()
            if not ok:
                continue
            esc = 640 / f.shape[1]
            g = cv2.cvtColor(cv2.resize(f, None, fx=esc, fy=esc), cv2.COLOR_BGR2GRAY)
            faces = casc_r.detectMultiScale(g, 1.1, 6, minSize=(40, 40))
            if not len(faces):
                continue
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            olhos = casc_o.detectMultiScale(g[y:y + h // 2 + h // 8, x:x + w], 1.1, 8, minSize=(w // 10, w // 10))
            if len(olhos) >= 2:
                return t
    finally:
        cap.release()
    return candidatos[0] if candidatos else 0.0


class Trilha:
    """Centro do rosto ao longo do tempo, interpolado e suavizado (sem tremedeira)."""

    def __init__(self, dados: dict, suavizar_s: float = 1.2):
        self.dados = dados
        med = dados["mediana"]
        a = np.array(dados.get("amostras") or [])
        if len(a) >= 2:
            dur = max(dados.get("duracao") or a[-1, 0], a[-1, 0])
            self.t = np.arange(0, dur + 0.05, 0.05)
            cx = np.interp(self.t, a[:, 0], a[:, 1])
            cy = np.interp(self.t, a[:, 0], a[:, 2])
            k = max(1, int(suavizar_s / 0.05))
            ker = np.ones(k) / k
            pad = k // 2
            self.cx = np.convolve(np.pad(cx, pad, mode="edge"), ker, mode="same")[pad:pad + len(cx)]
            self.cy = np.convolve(np.pad(cy, pad, mode="edge"), ker, mode="same")[pad:pad + len(cy)]
        else:
            self.t = np.array([0.0, 1.0])
            self.cx = np.array([med["cx"], med["cx"]], dtype=float)
            self.cy = np.array([med["cy"], med["cy"]], dtype=float)

    def centro(self, t: float) -> tuple[float, float]:
        return float(np.interp(t, self.t, self.cx)), float(np.interp(t, self.t, self.cy))

    def tamanho(self) -> tuple[float, float]:
        m = self.dados["mediana"]
        return float(m["w"]), float(m["h"])

    def fracao_fora(self, x0: float, largura: float) -> float:
        """Fração das amostras em que o rosto sai de uma janela horizontal [x0, x0+largura]."""
        a = np.array(self.dados.get("amostras") or [])
        if not len(a):
            return 0.0
        fora = ((a[:, 1] - a[:, 3] / 2) < x0) | ((a[:, 1] + a[:, 3] / 2) > x0 + largura)
        return float(fora.mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--saida", type=Path)
    args = ap.parse_args()
    d = rastrear(args.video, args.saida)
    print(f"{len(d['amostras'])} detecções; rosto mediano {d['mediana']}")


if __name__ == "__main__":
    main()
