"""Ícones locais (Phosphor Icons, licença MIT, instalados pelo npm). Sem API e sem internet.

  indexar                     gera motion/icones/indice.json (nomes + tags) a partir do pacote npm
  buscar "dinheiro vendas"    os 5 ícones mais prováveis para os termos (português ou inglês)
  svg <nome> [--estilo linha|preenchido|duotone]   imprime o SVG

Estilos de ícone: linha (Phosphor light), preenchido (fill), duotone, emoji, nenhum.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "node_modules" / "@phosphor-icons" / "core"
INDICE = RAIZ / "motion" / "icones" / "indice.json"
PT_EN = RAIZ / "motion" / "icones" / "pt-en.json"

PESO = {"linha": "light", "preenchido": "fill", "duotone": "duotone", "regular": "regular", "negrito": "bold"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def indexar() -> int:
    js = ("import('@phosphor-icons/core').then(m => { const l = (m.icons || m.default || []).map(i => "
          "({n: i.name, t: i.tags.filter(x => !x.startsWith('*')), c: i.categories})); "
          "process.stdout.write(JSON.stringify(l)); })")
    r = subprocess.run(["node", "-e", js], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode or not r.stdout:
        print("não consegui ler o pacote de ícones (rode: editor.py instalar)", file=sys.stderr)
        return 1
    icones = json.loads(r.stdout)
    INDICE.parent.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(icones, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"índice de ícones: {len(icones)} ícones → {INDICE.relative_to(RAIZ)}")
    return 0


def _carregar() -> list[dict]:
    if not INDICE.exists() and indexar():
        return []
    return json.loads(INDICE.read_text(encoding="utf-8"))


def buscar(termos: str, n: int = 5) -> list[tuple[str, float]]:
    icones = _carregar()
    mapa = {k: v for k, v in json.loads(PT_EN.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    palavras = [p for p in re.split(r"[^\w-]+", _norm(termos)) if len(p) > 1]
    # termos em inglês com peso: nomes do mapa valem mais que a palavra original
    alvos: dict[str, float] = {}
    for p in palavras:
        for cand in (p, p.rstrip("s")):
            for i, en in enumerate(mapa.get(cand, [])):
                alvos[en] = max(alvos.get(en, 0), 3.0 - i * 0.4)
        alvos.setdefault(p, 1.0)
    pontos: dict[str, float] = {}
    for ic in icones:
        nome, tags = ic["n"], [_norm(t) for t in ic.get("t", [])]
        partes = nome.split("-")
        s = 0.0
        for alvo, peso in alvos.items():
            if nome == alvo:
                s += 10 * peso
            elif alvo in partes or nome.startswith(alvo + "-"):
                s += 4 * peso
            elif alvo in tags:
                s += 2.5 * peso
            elif len(alvo) > 3 and any(alvo in t for t in tags):
                s += 0.8 * peso
        if s:
            # nomes curtos (ícone "principal") ganham desempate; logos de marca só se pedidos
            s -= 0.15 * len(partes)
            if nome.endswith("-logo") and not any(a in nome for a in alvos):
                s -= 3
            if partes[-1] in {"slash", "x", "minus", "dashed"} and partes[-1] not in alvos:
                s -= 4
            pontos[nome] = s
    return sorted(pontos.items(), key=lambda x: -x[1])[:n]


def svg(nome: str, estilo: str = "linha") -> str:
    peso = PESO.get(estilo, estilo)
    arq = PACOTE / "assets" / peso / (f"{nome}.svg" if peso == "regular" else f"{nome}-{peso}.svg")
    if not arq.exists():
        raise SystemExit(f"ícone não encontrado: {nome} ({peso})")
    texto = arq.read_text(encoding="utf-8")
    return texto.replace("<svg ", '<svg class="icone" aria-hidden="true" ', 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("indexar")
    b = sub.add_parser("buscar")
    b.add_argument("termos", nargs="+")
    b.add_argument("-n", type=int, default=5)
    b.add_argument("--json", action="store_true")
    s = sub.add_parser("svg")
    s.add_argument("nome")
    s.add_argument("--estilo", default="linha")
    a = ap.parse_args()
    if a.cmd == "indexar":
        return indexar()
    if a.cmd == "buscar":
        res = buscar(" ".join(a.termos), a.n)
        if a.json:
            print(json.dumps([r[0] for r in res]))
        else:
            for nome, s in res:
                print(f"{nome}  ({s:.1f})")
        return 0
    print(svg(a.nome, a.estilo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
