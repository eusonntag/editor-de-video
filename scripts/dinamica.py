"""Edição dinâmica: zooms descritos em <trabalho>/dinamica.json, aplicados pelo layout.py.

Tipos de evento {inicio, fim, tipo, intensidade, ativo, motivo}:
  punch        salto de enquadramento a cada corte (100% ↔ ~112%), disfarça o "pulo" do jump cut
  enfase       zoom rápido (~120%) numa frase importante, sincronizado pelo palavras.json
  aproximacao  aproximação lenta e contínua em trechos longos sem corte

Estilos:
  natural    sem zoom
  dinamica   punch a cada corte + 1 ênfase a cada ~12 s nas frases-chave
  acelerada  punch em todo corte, ênfase a cada ~7 s e aproximação nos trechos longos
             (as pausas mais curtas são aplicadas antes, no corte: --pausa 0.2)

Tempos na linha do tempo do vídeo CORTADO (o layout não muda a duração).

Uso:
  python -X utf8 scripts/dinamica.py <trabalho> --estilo dinamica
  python -X utf8 scripts/dinamica.py <trabalho> --listar          (lista os zooms em texto simples)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import fmt_tempo, info_video  # noqa: E402

PALAVRAS_FORTES = {
    "importante", "segredo", "nunca", "sempre", "principal", "erro", "erros", "dica", "dicas",
    "atencao", "olha", "resultado", "resultados", "gratis", "rapido", "melhor", "pior", "maior",
    "menor", "unico", "unica", "verdade", "problema", "solucao", "cuidado", "simples", "facil",
    "dinheiro", "vender", "vendas", "lucro", "agora", "hoje", "ninguem", "todo", "todos", "tudo",
    "primeiro", "segundo", "terceiro", "ultimo", "porque", "funciona", "muda", "mudou", "incrivel",
}
NUMEROS = {"um", "uma", "dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove",
           "dez", "vinte", "trinta", "cem", "cento", "mil", "milhao", "milhoes", "bilhao", "metade", "dobro"}

REGRAS = {
    "natural": {"punch": 0.0, "enfase_cada": 0, "aproximacao": False},
    "dinamica": {"punch": 1.12, "enfase_cada": 12.0, "enfase": 1.20, "aproximacao": False},
    "acelerada": {"punch": 1.12, "enfase_cada": 7.0, "enfase": 1.22, "aproximacao": True},
}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^\w%$]", "", "".join(c for c in t if not unicodedata.combining(c)))


def tempos_de_corte(trab: Path) -> list[float]:
    """Instantes (no vídeo cortado) em que um trecho do EDL termina e o próximo começa."""
    from palavras_timeline import duracoes_reais

    edit = trab / "edit"
    edl = json.loads((edit / "edl.json").read_text(encoding="utf-8"))
    ranges = edl["ranges"]
    reais = duracoes_reais(edit, len(ranges))
    cortes, t = [], 0.0
    for i, r in enumerate(ranges[:-1]):
        t += reais[i] if reais else float(r["end"]) - float(r["start"])
        cortes.append(round(t, 3))
    return cortes


def frases(palavras: list[dict], pausa: float = 0.35) -> list[list[dict]]:
    out: list[list[dict]] = []
    for w in palavras:
        if out and w["start"] - out[-1][-1]["end"] <= pausa and not out[-1][-1]["text"].endswith((".", "!", "?", ",")):
            out[-1].append(w)
        else:
            out.append([w])
    return out


def pontuar_frase(f: list[dict]) -> tuple[float, int]:
    """Nota da frase e índice da palavra-chave (onde o zoom chega)."""
    melhor, idx = 0.0, 0
    for i, w in enumerate(f):
        n = _norm(w["text"])
        s = 0.0
        if re.search(r"\d", n) or n in NUMEROS or "%" in n or "$" in n:
            s = 3.0
        elif n in PALAVRAS_FORTES:
            s = 2.0
        elif len(n) >= 9:
            s = 0.6
        if s > melhor:
            melhor, idx = s, i
    texto = " ".join(w["text"] for w in f)
    if texto.endswith("!"):
        melhor += 1.5
    elif texto.endswith("?"):
        melhor += 0.8
    if 2 <= len(f) <= 8:
        melhor += 0.5
    return melhor, idx


def hash_edl(trab: Path) -> str:
    import hashlib

    edl = json.loads((trab / "edit" / "edl.json").read_text(encoding="utf-8"))
    chave = json.dumps([[r["source"], r["start"], r["end"]] for r in edl["ranges"]])
    return hashlib.sha1(chave.encode()).hexdigest()[:12]


def video_atual(trab: Path) -> Path:
    """cortado.mp4 se estiver em dia com o EDL; senão o rascunho."""
    edl = trab / "edit" / "edl.json"
    cortado, rascunho = trab / "cortado.mp4", trab / "rascunho.mp4"
    if cortado.exists() and (not rascunho.exists() or cortado.stat().st_mtime >= edl.stat().st_mtime):
        return cortado
    return rascunho if rascunho.exists() else cortado


def gerar(trab: Path, estilo: str) -> dict:
    regras = REGRAS[estilo]
    palavras = json.loads((trab / "palavras.json").read_text(encoding="utf-8"))
    dur = info_video(video_atual(trab))["duracao"]
    cortes = tempos_de_corte(trab)
    eventos: list[dict] = []

    if regras["punch"]:
        limites = [0.0, *cortes, dur]
        nivel_alto = False
        for i in range(len(limites) - 1):
            a, b = limites[i], limites[i + 1]
            if b - a < 0.6 and i > 0:
                continue  # trecho curto demais: mantém o enquadramento anterior (evita piscar)
            nivel_alto = not nivel_alto if i > 0 else False
            if nivel_alto:
                eventos.append({"inicio": round(a, 3), "fim": round(b, 3), "tipo": "punch",
                                "intensidade": regras["punch"], "ativo": True, "motivo": f"corte {i}"})
            if regras["aproximacao"] and b - a >= 4.0:
                eventos.append({"inicio": round(a, 3), "fim": round(b, 3), "tipo": "aproximacao",
                                "intensidade": 1.06, "ativo": True, "motivo": f"trecho longo de {b - a:.0f} s"})

    if regras["enfase_cada"]:
        candidatos = []
        for f in frases(palavras):
            nota, i = pontuar_frase(f)
            if nota >= 2.0:
                ini = max(0.0, f[i]["start"] - 0.12)
                fim = min(dur, max(f[-1]["end"] + 0.15, ini + 0.9))
                fim = min(fim, ini + 2.6)
                candidatos.append((nota, ini, fim, " ".join(w["text"] for w in f[i:i + 5])))
        escolhidos: list[tuple] = []
        for c in sorted(candidatos, key=lambda c: -c[0]):
            if all(abs(c[1] - e[1]) >= regras["enfase_cada"] for e in escolhidos):
                escolhidos.append(c)
            if len(escolhidos) >= max(1, int(dur / regras["enfase_cada"])):
                break
        for nota, ini, fim, texto in sorted(escolhidos, key=lambda c: c[1]):
            eventos.append({"inicio": round(ini, 3), "fim": round(fim, 3), "tipo": "enfase",
                            "intensidade": regras["enfase"], "ativo": True, "texto": texto.strip(" ,.")})

    eventos.sort(key=lambda e: (e["inicio"], e["tipo"]))
    return {"estilo": estilo, "edl_hash": hash_edl(trab), "duracao": round(dur, 3), "cortes": cortes, "eventos": eventos}


def listar(d: dict) -> str:
    nomes = {"punch": "zoom de corte", "enfase": "zoom de ênfase", "aproximacao": "aproximação lenta"}
    linhas = []
    for e in d.get("eventos", []):
        if not e.get("ativo", True):
            continue
        extra = f" em \"{e['texto']}\"" if e.get("texto") else ""
        linhas.append(f"{fmt_tempo(e['inicio'])} {nomes[e['tipo']]}{extra} ({round((e['intensidade'] - 1) * 100)}%)")
    return "\n".join(linhas) if linhas else "(sem zooms)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trabalho", type=Path)
    ap.add_argument("--estilo", choices=list(REGRAS))
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    destino = a.trabalho / "dinamica.json"
    if a.estilo:
        d = gerar(a.trabalho, a.estilo)
        destino.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        n = {t: sum(1 for e in d["eventos"] if e["tipo"] == t) for t in ("punch", "enfase", "aproximacao")}
        print(f"edição {a.estilo}: {n['punch']} zooms de corte, {n['enfase']} ênfases, {n['aproximacao']} aproximações → {destino}")
    if a.listar or not a.estilo:
        d = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {"eventos": []}
        print(listar(d))


if __name__ == "__main__":
    main()
