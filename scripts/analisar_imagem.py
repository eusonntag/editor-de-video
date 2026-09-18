"""Mede cor e exposição de um vídeo e diz se vale oferecer correção de cor.

Métricas (em quadros espalhados pelo vídeo):
  - pele: média RGB na região do rosto (pele saudável tem R > G > B)
  - neutro: média RGB do quadro inteiro (mundo cinza) para achar tom azulado/amarelado
  - exposição: percentis de luminância (p2, p50, p98), % de pixels estourados (>=250) e esmagados (<=5)
  - estouro na cabeça: % de pixels >=250 na região do rosto/testa

Saída JSON com "problemas" (lista em linguagem simples) e "sugestao" (filtro ffmpeg para o
campo "grade" do edl.json). Com --comparar, gera uma imagem antes/depois para aprovação.

Uso:
  python -X utf8 scripts/analisar_imagem.py video.mp4 [--rosto rosto.json] [--comparar saida.jpg]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import FONTES, info_video  # noqa: E402
from rosto import rastrear  # noqa: E402

# filtro de referência (webcam fria e escura), validado no projeto em 2026-09-18
REF_FRIA_ESCURA = ("colorbalance=rs=0.04:bs=-0.07:rm=0.07:gm=0.02:bm=-0.12:rh=0.05:gh=0.02:bh=-0.10,"
                   "curves=master='0/0 0.25/0.29 0.5/0.56 0.75/0.8 1/1',eq=contrast=1.04:saturation=1.08")


def quadros(video: Path, n: int = 6, filtro: str | None = None) -> list[np.ndarray]:
    import cv2

    dur = info_video(video)["duracao"]
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            t = dur * (i + 0.5) / n
            png = Path(tmp) / f"q{i}.png"
            cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1"]
            if filtro:
                cmd += ["-vf", filtro]
            subprocess.run(cmd + [str(png)], check=True)
            img = cv2.imread(str(png))
            if img is not None:
                out.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    return out


def medir(imgs: list[np.ndarray], caixa: tuple[int, int, int, int] | None) -> dict:
    todos = np.concatenate([im.reshape(-1, 3) for im in imgs]).astype(np.float64)
    lum = todos @ np.array([0.2126, 0.7152, 0.0722])
    m = {
        "media_rgb": [round(float(v), 1) for v in todos.mean(axis=0)],
        "lum_p2": round(float(np.percentile(lum, 2)), 1),
        "lum_p50": round(float(np.percentile(lum, 50)), 1),
        "lum_p98": round(float(np.percentile(lum, 98)), 1),
        "estourado_pct": round(float((todos.max(axis=1) >= 250).mean() * 100), 2),
        "esmagado_pct": round(float((todos.max(axis=1) <= 5).mean() * 100), 2),
    }
    if caixa:
        x, y, w, h = caixa
        # centro do rosto (bochechas/nariz): evita barba, olhos e fundo
        px = np.concatenate([im[y + int(h * .35):y + int(h * .65), x + int(w * .25):x + int(w * .75)].reshape(-1, 3)
                             for im in imgs]).astype(np.float64)
        testa = np.concatenate([im[max(0, y - int(h * .25)):y + int(h * .2), x:x + w].reshape(-1, 3)
                                for im in imgs]).astype(np.float64)
        if len(px):
            m["pele_rgb"] = [round(float(v), 1) for v in px.mean(axis=0)]
        if len(testa):
            m["estouro_cabeca_pct"] = round(float((testa.max(axis=1) >= 250).mean() * 100), 2)
    return m


def diagnosticar(m: dict) -> tuple[list[str], str | None]:
    problemas: list[str] = []
    r, g, b = m.get("pele_rgb") or m["media_rgb"]
    R, G, B = m["media_rgb"]
    fria = (b >= r - 4) or (B - R > 8)
    quente = (r - b > 70) or (R - B > 45)
    escura = m["lum_p98"] < 200 or m["lum_p50"] < 70
    clara = m["lum_p50"] > 175 or m["estourado_pct"] > 4
    lavada = m["lum_p2"] > 35
    if fria:
        problemas.append("tom frio/azulado (pele sem calor)")
    if quente:
        problemas.append("tom amarelado/alaranjado demais")
    if escura:
        problemas.append("imagem escura")
    if clara:
        problemas.append("imagem clara demais ou estourada")
    if lavada:
        problemas.append("pretos lavados (pouco contraste)")
    if not problemas:
        return [], None
    partes = []
    if fria and escura:
        return problemas, REF_FRIA_ESCURA
    if fria:
        partes.append("colorbalance=rs=0.03:bs=-0.06:rm=0.06:bm=-0.10:rh=0.04:bh=-0.08")
    if quente:
        partes.append("colorbalance=rs=-0.04:bs=0.05:rm=-0.05:bm=0.06:rh=-0.03:bh=0.05")
    if escura:
        partes.append("curves=master='0/0 0.25/0.30 0.5/0.57 0.75/0.81 1/1'")
    if clara:
        partes.append("curves=master='0/0 0.25/0.22 0.5/0.46 0.75/0.72 1/0.96'")
    if lavada:
        partes.append("curves=master='0/0 0.08/0.03 0.5/0.5 1/1'")
    partes.append("eq=contrast=1.03:saturation=1.05")
    return problemas, ",".join(partes)


def comparar(video: Path, filtro: str, destino: Path) -> None:
    """Imagem com 3 momentos do vídeo: original em cima, corrigido embaixo."""
    dur = info_video(video)["duracao"]
    ts = [dur * f for f in (0.2, 0.5, 0.8)]
    with tempfile.TemporaryDirectory() as tmp:
        arqs = []
        for i, t in enumerate(ts):
            for tipo, vf in (("a", "scale=640:-2"), ("d", f"{filtro},scale=640:-2")):
                p = Path(tmp) / f"{tipo}{i}.png"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                                "-frames:v", "1", "-vf", vf, str(p)], check=True)
                arqs.append(p)
        entradas = []
        for p in arqs:
            entradas += ["-i", str(p)]
        rot = "fontfile=Inter-700.ttf:x=20:y=20:fontsize=36:fontcolor=white:box=1:boxcolor=black@0.6"
        fc = (f"[0][2][4]hstack=3,drawtext=text='ANTES':{rot}[a];"
              f"[1][3][5]hstack=3,drawtext=text='DEPOIS':{rot}[d];[a][d]vstack")
        # roda na pasta das fontes: evita o fontconfig e o escape de "C:" no caminho
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", fc, str(destino.resolve())],
                           cwd=FONTES)
        if r.returncode:  # ffmpeg sem drawtext (fontconfig): sem os rótulos
            fc = "[0][2][4]hstack=3[a];[1][3][5]hstack=3[d];[a][d]vstack"
            subprocess.run(["ffmpeg", "-v", "error", "-y", *entradas, "-filter_complex", fc, str(destino)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--rosto", type=Path, help="cache do rosto (padrão: ao lado do vídeo de trabalho)")
    ap.add_argument("--filtro", help="Mede com este filtro aplicado (para conferir uma correção)")
    ap.add_argument("--comparar", type=Path, help="Gera imagem antes/depois com o filtro sugerido (ou --filtro)")
    a = ap.parse_args()

    dados = rastrear(a.video, a.rosto)
    med = dados["mediana"]
    caixa = None if dados.get("sem_rosto") else (int(med["cx"] - med["w"] / 2), int(med["cy"] - med["h"] / 2),
                                                  int(med["w"]), int(med["h"]))
    imgs = quadros(a.video, filtro=a.filtro)
    m = medir(imgs, caixa)
    problemas, sugestao = diagnosticar(m)
    res = {"metricas": m, "problemas": problemas, "sugestao": a.filtro or sugestao,
           "precisa_corrigir": bool(problemas)}
    if a.filtro or sugestao:
        depois = medir(quadros(a.video, filtro=a.filtro or sugestao), caixa)
        res["metricas_depois"] = depois
        antes_c, depois_c = m.get("estouro_cabeca_pct", 0), depois.get("estouro_cabeca_pct", 0)
        res["estouro_novo"] = depois_c > antes_c + 0.5
    if a.comparar and (a.filtro or sugestao):
        comparar(a.video, a.filtro or sugestao, a.comparar)
        res["comparacao"] = str(a.comparar)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
