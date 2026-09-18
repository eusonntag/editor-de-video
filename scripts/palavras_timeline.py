"""Converte as palavras da transcrição original para a linha do tempo do vídeo CORTADO.

output_time = word.start - segment_start + segment_offset   (regra 5 do video-use)

Assim legendas e animações do HyperFrames ficam sincronizadas com o vídeo editado
sem precisar transcrever de novo.

Saída: JSON plano [{ "text", "start", "end" }, ...] (mesmo formato do transcript.json
do HyperFrames).

Uso:
  python -X utf8 scripts/palavras_timeline.py trabalho/video/edit/edl.json -o trabalho/video/palavras.json
  python -X utf8 scripts/palavras_timeline.py edl.json --ver 10 25     (lista palavras da ORIGEM entre 10s e 25s)
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def duracoes_reais(edit_dir: Path, n: int, pasta: str | None = None) -> list[float] | None:
    """Duração real de cada segmento renderizado pelo render.py (clips_graded/seg_NN_*.mp4).

    O render arredonda cada segmento de vídeo para cima até o próximo frame; com centenas
    de cortes isso acumula segundos. O concat do ffmpeg desloca cada segmento pela duração
    real, então é ela que define onde cada palavra cai no vídeo final.
    """
    if pasta is None:
        # o corte final (clips_graded) vale mais; o rascunho (clips_draft) tem as mesmas durações por quadro
        return duracoes_reais(edit_dir, n, "clips_graded") or duracoes_reais(edit_dir, n, "clips_draft")
    clips = sorted((edit_dir / pasta).glob("seg_*.mp4"))
    if len(clips) != n:
        return None
    duracoes = []
    for c in clips:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(c)],
            capture_output=True, text=True, check=True)
        duracoes.append(float(out.stdout.strip()))
    return duracoes


def carregar_palavras(edit_dir: Path, fonte: str) -> list[dict]:
    dados = json.loads((edit_dir / "transcripts" / f"{fonte}.json").read_text(encoding="utf-8"))
    return [w for w in dados.get("words", [])
            if w.get("type", "word") == "word" and w.get("start") is not None]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    ap.add_argument("-o", "--saida", type=Path)
    ap.add_argument("--ver", nargs=2, type=float, metavar=("INICIO", "FIM"),
                    help="Só lista as palavras da origem nesse intervalo, com tempos")
    args = ap.parse_args()

    edl_path = args.edl.resolve()
    edit_dir = edl_path.parent
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    cache: dict[str, list[dict]] = {}

    if args.ver:
        a, b = args.ver
        for fonte in edl["sources"]:
            for w in carregar_palavras(edit_dir, fonte):
                if w["end"] >= a and w["start"] <= b:
                    print(f"{w['start']:8.3f}-{w['end']:8.3f}  {w['text']}")
        return

    saida: list[dict] = []
    offset = 0.0
    reais = duracoes_reais(edit_dir, len(edl["ranges"]))
    print("offsets: " + ("durações reais dos trechos renderizados" if reais else
                         "EDL (trechos ainda não renderizados: tempos aproximados)"))
    for idx, r in enumerate(edl["ranges"]):
        fonte = r["source"]
        if fonte not in cache:
            cache[fonte] = carregar_palavras(edit_dir, fonte)
        ini, fim = float(r["start"]), float(r["end"])
        for w in cache[fonte]:
            # palavra conta se o meio dela está dentro do trecho mantido
            meio = (w["start"] + w["end"]) / 2
            if ini <= meio <= fim:
                s = max(w["start"], ini) - ini + offset
                e = min(w["end"], fim) - ini + offset
                texto = w["text"].strip()
                # símbolo solto ("%", "R$"...) gruda na palavra anterior: "40 %" -> "40%"
                if saida and not any(c.isalnum() for c in texto):
                    saida[-1]["text"] += texto
                    saida[-1]["end"] = round(e, 3)
                    continue
                saida.append({"text": texto, "start": round(s, 3), "end": round(e, 3)})
        offset += reais[idx] if reais else fim - ini

    # correções de transcrição persistentes: edit/correcoes.json = {"errado": "Certo", ...}
    # (compara sem pontuação/maiúsculas e preserva a pontuação original da palavra)
    corr_path = edit_dir / "correcoes.json"
    if corr_path.exists():
        correcoes = {k.lower(): v for k, v in json.loads(corr_path.read_text(encoding="utf-8")).items()}
        n = 0
        for w in saida:
            nucleo = w["text"].strip(".,!?;:…\"'")
            if nucleo.lower() in correcoes:
                w["text"] = w["text"].replace(nucleo, correcoes[nucleo.lower()])
                n += 1
        print(f"correções aplicadas: {n}")

    destino = args.saida or (edit_dir.parent / "palavras.json")
    destino.write_text(json.dumps(saida, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(saida)} palavras na linha do tempo editada ({offset:.2f}s) → {destino}")


if __name__ == "__main__":
    main()
