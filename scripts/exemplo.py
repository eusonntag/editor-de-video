"""Teste completo do editor com o vídeo de exemplo (sem API, sem custo).

Usa exemplo/video.mp4 + exemplo/transcricao.json (transcrição pronta) + exemplo/roteiro.json e passa
por todas as etapas: base do corte → corte (tira a frase repetida) → zooms → layout → motion →
legenda → salva em videos/Editados/exemplo_editado.mp4.

Uso: editor.py exemplo   (ou python -X utf8 scripts/exemplo.py [--sem-motion])
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa: E402

EX = C.RAIZ / "exemplo"
TRAB = C.TRABALHO / "_exemplo"


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^\w ]", "", "".join(c for c in t if not unicodedata.combining(c))).strip()


def passo(n: int, total: int, texto: str) -> None:
    print(f"⏳ Passo {n}/{total}: {texto}.", flush=True)


def cortar_repeticoes(edl_arq: Path) -> int:
    """O que o Claude faria na revisão: some com a primeira versão de uma frase refeita."""
    edl = json.loads(edl_arq.read_text(encoding="utf-8"))
    rs = edl["ranges"]
    manter = []
    for i, r in enumerate(rs):
        prox = rs[i + 1]["quote"] if i + 1 < len(rs) else ""
        if prox and _n(prox).startswith(_n(r["quote"])) and len(_n(r["quote"])) > 6:
            continue
        manter.append(r)
    removidos = len(rs) - len(manter)
    edl["ranges"] = manter
    edl_arq.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    return removidos


def roteiro_com_tempos(palavras: list[dict]) -> dict:
    rot = json.loads((EX / "roteiro.json").read_text(encoding="utf-8"))
    rot.pop("_obs", None)
    marca = C.ler_marca()
    rot["estilo"] = rot.get("estilo") or (marca.get("motion") or {}).get("estilo") or "escuro"
    rot["icones"] = rot.get("icones") or (marca.get("motion") or {}).get("icones") or None
    if not rot["icones"]:
        rot.pop("icones")

    def achar(txt: str, depois: float) -> dict:
        alvo = _n(txt)
        for w in palavras:
            if w["start"] >= depois - 0.05 and _n(w["text"]) == alvo:
                return w
        raise SystemExit(f"palavra do roteiro não encontrada: {txt}")

    t = 0.0
    for c in rot["cards"]:
        a = achar(c.pop("de"), t)
        b = achar(c.pop("ate"), a["start"])
        c["inicio"] = round(max(0.0, a["start"] - 0.25), 3)
        c["fim"] = round(b["end"] + 0.5, 3)
        t = b["end"]
    dur = palavras[-1]["end"] + 1.0
    rot["cards"][-1]["fim"] = round(min(dur, rot["cards"][-1]["fim"] + 5), 3)
    for c, prox in zip(rot["cards"], rot["cards"][1:]):
        c["fim"] = round(min(c["fim"], prox["inicio"] - 0.05), 3)  # um card de cada vez
    return rot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-motion", action="store_true", help="pula o motion (teste rápido)")
    a = ap.parse_args()
    t0 = time.time()
    total = 5 if a.sem_motion else 6
    video = EX / "video.mp4"
    if not video.exists():
        raise SystemExit("falta exemplo/video.mp4 (baixe o projeto de novo)")
    if TRAB.exists():
        shutil.rmtree(TRAB)
    (TRAB / "edit" / "transcripts").mkdir(parents=True)
    shutil.copy2(EX / "transcricao.json", TRAB / "edit" / "transcripts" / f"{video.stem}.json")

    passo(1, total, "achar as pausas e a frase repetida")
    C.rodar_script("scripts/edl_base.py", str(video), "--edit-dir", str(TRAB / "edit"))
    removidos = cortar_repeticoes(TRAB / "edit" / "edl.json")

    passo(2, total, "cortar o vídeo")
    render = C.TOOLS / "video-use" / "helpers" / "render.py"
    C.rodar_script(str(render.relative_to(C.RAIZ)), str(TRAB / "edit" / "edl.json"), "-o", str(TRAB / "cortado.mp4"),
                   "--no-subtitles", quieto=True)
    C.rodar_script("scripts/palavras_timeline.py", str(TRAB / "edit" / "edl.json"))

    passo(3, total, "aplicar os zooms da edição dinâmica")
    C.rodar_script("scripts/dinamica.py", str(TRAB), "--estilo", "dinamica")
    C.rodar_script("scripts/layout.py", str(TRAB), "horizontal")

    formato_final = TRAB / "horizontal" / "base.mp4"
    n = 4
    if not a.sem_motion:
        passo(n, total, "gerar as animações")
        palavras = json.loads((TRAB / "palavras.json").read_text(encoding="utf-8"))
        C.gravar_json(TRAB / "motion" / "roteiro.json", roteiro_com_tempos(palavras))
        C.rodar_script("scripts/motion.py", "montar", str(TRAB), "--formato", "horizontal")
        C.rodar_script("scripts/motion.py", "render", str(TRAB), "--formato", "horizontal")
        formato_final = TRAB / "horizontal" / "animado.mp4"
        n += 1

    passo(n, total, "colocar a legenda")
    lay = json.loads((TRAB / "horizontal" / "layout.json").read_text(encoding="utf-8"))
    final = TRAB / "horizontal" / "final.mp4"
    C.rodar_script("scripts/legendas.py", str(TRAB / "palavras.json"), "--video", str(formato_final),
                   "--saida-ass", str(TRAB / "horizontal" / "legendas.ass"), "--queimar", str(final),
                   "--margem-v", str(lay["legenda"]["margem_v"]))

    passo(n + 1, total, "salvar e conferir")
    destino = C.EDITADOS / "exemplo_editado.mp4"
    C.copiar(final, destino)
    info = C.info_video(destino)
    ref = C.info_video(TRAB / "cortado.mp4")["duracao"]
    ok = info["tem_audio"] and abs(info["duracao"] - ref) < 0.5
    import subprocess

    quadros = TRAB / "verificacao.jpg"
    tmp = [TRAB / f"q{i}.png" for i in range(3)]
    for i, tt in enumerate((ref * 0.2, ref * 0.5, ref * 0.8)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tt:.2f}", "-i", str(destino), "-frames:v", "1",
                        "-vf", "scale=-2:360", str(tmp[i])], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp[0]), "-i", str(tmp[1]), "-i", str(tmp[2]),
                    "-filter_complex", "hstack=inputs=3", str(quadros)], check=True)
    for p in tmp:
        p.unlink(missing_ok=True)
    print(json.dumps({"ok": ok, "arquivo": str(destino), "duracao_original": round(C.info_video(video)["duracao"], 1),
                      "duracao_final": round(info["duracao"], 1), "frases_repetidas_removidas": removidos,
                      "audio": info["tem_audio"], "quadros": str(quadros),
                      "tempo_total_s": round(time.time() - t0)}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
