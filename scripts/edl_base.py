"""Gera um EDL base (formato video-use) que remove TODOS os silêncios de um vídeo.

Agrupa as palavras da transcrição em trechos contínuos de fala; qualquer pausa maior
que --pausa vira um corte. Cada borda de corte recebe padding (regra 7 do video-use)
e cai sempre entre palavras (regra 6).

Também sinaliza, para revisão, trechos suspeitos de erro:
  - hesitações isoladas ("é", "hã", "hum"...)
  - repetições / frases refeitas (o início de um trecho repete palavras do anterior,
    ou a mesma sequência de palavras aparece duas vezes seguidas)

Saídas em <edit-dir>:
  edl.json      -> EDL pronto para tools/video-use/helpers/render.py
  revisao.md    -> lista numerada dos trechos com alertas (leitura para decidir cortes)

Uso:
  python -X utf8 scripts/edl_base.py "Para Editar/video.mp4" --edit-dir trabalho/video/edit
  opções: --pausa 0.35 --pad-in 0.08 --pad-out 0.12
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import unicodedata
from pathlib import Path

HESITACOES = {"é", "eh", "hã", "ha", "hum", "hm", "hmm", "ahn", "ah", "uh", "um", "ã", "éé", "ééé"}


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", t)


def duracao_video(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def repeticao_interna(palavras: list[str], n_min: int = 2) -> str | None:
    """Procura uma sequência de n palavras repetida imediatamente ("eu fui eu fui")."""
    for n in range(4, n_min - 1, -1):
        for i in range(len(palavras) - 2 * n + 1):
            a = palavras[i:i + n]
            b = palavras[i + n:i + 2 * n]
            if a == b and any(len(p) > 2 for p in a):
                return " ".join(a)
    # repetição de uma palavra longa ("mercado mercado")
    for i in range(len(palavras) - 1):
        if palavras[i] == palavras[i + 1] and len(palavras[i]) > 3:
            return palavras[i]
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="EDL base sem silêncios + alertas de repetição")
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("--pausa", type=float, default=0.35,
                    help="Pausas maiores que isso (s) são cortadas. Padrão 0.35")
    ap.add_argument("--pad-in", type=float, default=0.08, help="Folga antes da 1ª palavra (s)")
    ap.add_argument("--pad-out", type=float, default=0.12, help="Folga depois da última palavra (s)")
    args = ap.parse_args()

    video = args.video.resolve()
    edit_dir = args.edit_dir.resolve()
    transcript = edit_dir / "transcripts" / f"{video.stem}.json"
    dados = json.loads(transcript.read_text(encoding="utf-8"))
    palavras = [w for w in dados.get("words", [])
                if w.get("type", "word") == "word" and w.get("start") is not None]
    if not palavras:
        raise SystemExit("transcrição sem palavras")
    dur = duracao_video(video)

    # 1. agrupar em trechos contínuos de fala
    grupos: list[list[dict]] = [[palavras[0]]]
    for w in palavras[1:]:
        if w["start"] - grupos[-1][-1]["end"] > args.pausa:
            grupos.append([w])
        else:
            grupos[-1].append(w)

    # 2. transformar em ranges com padding sem sobreposição
    ranges: list[dict] = []
    for i, g in enumerate(grupos):
        ini = max(0.0, g[0]["start"] - args.pad_in)
        fim = min(dur, g[-1]["end"] + args.pad_out)
        if ranges and ini < ranges[-1]["end"]:
            meio = (ranges[-1]["end"] + ini) / 2
            ranges[-1]["end"] = round(meio, 3)
            ini = meio
        texto = " ".join(w["text"].strip() for w in g)
        ranges.append({
            "id": i + 1,
            "source": video.stem,
            "start": round(ini, 3),
            "end": round(fim, 3),
            "quote": texto,
        })

    # 3. alertas para revisão
    for i, r in enumerate(ranges):
        alertas: list[str] = []
        norm = [normalizar(w["text"]) for w in grupos[i]]
        norm = [p for p in norm if p]
        if norm and all(p in HESITACOES for p in norm):
            alertas.append("hesitação isolada")
        rep = repeticao_interna(norm)
        if rep:
            alertas.append(f"repetição interna: \"{rep}\"")
        if i > 0 and len(norm) >= 2:
            ant = [p for p in (normalizar(w["text"]) for w in grupos[i - 1]) if p]
            inicio = norm[:3]
            texto_ant = " " + " ".join(ant) + " "
            if len(inicio) >= 2 and (" " + " ".join(inicio[:2]) + " ") in texto_ant:
                alertas.append(f"possível frase refeita (repete o trecho #{ranges[i-1]['id']})")
        if alertas:
            r["alerta"] = "; ".join(alertas)

    total = sum(r["end"] - r["start"] for r in ranges)
    edl = {
        "version": 1,
        "sources": {video.stem: str(video)},
        "ranges": ranges,
        "grade": "none",
        "overlays": [],
        "total_duration_s": round(total, 2),
    }
    (edit_dir / "edl.json").write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")

    linhas = [
        f"# Revisão de cortes — {video.name}",
        "",
        f"Original: {dur:.1f}s → sem silêncios: {total:.1f}s ({len(ranges)} trechos, pausa > {args.pausa}s cortada)",
        "",
        "Remova do edl.json os trechos com erro/repetição (manter sempre a ÚLTIMA versão de uma frase refeita).",
        "Para cortar só parte de um trecho, ajuste start/end usando os tempos das palavras na transcrição.",
        "",
    ]
    for r in ranges:
        d = r["end"] - r["start"]
        alerta = f"   ⚠ {r['alerta']}" if r.get("alerta") else ""
        linhas.append(f"#{r['id']:03d} [{r['start']:8.2f}-{r['end']:8.2f}] ({d:4.1f}s) {r['quote']}{alerta}")
    (edit_dir / "revisao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    n_alertas = sum(1 for r in ranges if r.get("alerta"))
    print(f"edl base: {len(ranges)} trechos, {dur:.1f}s → {total:.1f}s ({dur - total:.1f}s de silêncio removidos)")
    print(f"alertas para revisar: {n_alertas}  → {edit_dir / 'revisao.md'}")


if __name__ == "__main__":
    main()
