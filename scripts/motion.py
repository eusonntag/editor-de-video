"""Motion 2.0: o roteiro de cards (conteúdo) vira uma composição HyperFrames a partir de modelos
testados (visual). Claude escreve só o roteiro; o gerador cuida de HTML, animação, posição e fontes.

  montar  <trabalho> --formato F [--estilo X] [--icones Y]   gera <trabalho>/motion/<F>/public/ + lint
  previa  <trabalho> --formato F     folha com um quadro por card (a imagem que o aluno aprova)
  galeria <trabalho> --formato F [--tipo estilos|icones]   compara os 4 estilos (ou os 5 estilos de ícone)
  render  <trabalho> --formato F     gera <trabalho>/<F>/animado.mp4
  validar <trabalho>                 confere o roteiro (tipos, campos, tempos, palavras de sincronia)

Roteiro: <trabalho>/motion/roteiro.json
  {"estilo": "escuro", "icones": "duotone",
   "cards": [{"id": "card-01", "tipo": "lista", "inicio": 4.75, "fim": 13.99, "icone": "list-checks",
              "campos": {"titulo": "A função do projeto",
                         "itens": [{"texto": "Editar vídeos", "palavra": "editar"}, ...]}}]}
Tempos na linha do tempo do vídeo cortado (palavras.json). "palavra" sincroniza pelo momento
em que ela é falada (primeira ocorrência dentro do card); "em" força o segundo exato.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import FONTES, RAIZ, bin_hyperframes, info_video, ler_marca  # noqa: E402

MOTION = RAIZ / "motion"
MODELOS = MOTION / "modelos"
ESTILOS = MOTION / "estilos"
GSAP = RAIZ / "node_modules" / "gsap" / "dist" / "gsap.min.js"
TIPOS = ["apresentacao", "titulo", "lista", "numero", "destaque", "passos", "palavra", "chamada-final", "personalizado"]
ESTILOS_ICONE = ["linha", "preenchido", "duotone", "emoji", "nenhum"]
ACAO_ICONE = {"seguir": ("user-plus", "➕"), "comentar": ("chat-circle-dots", "💬"),
              "compartilhar": ("share-network", "📤"), "link": ("link", "🔗")}


# ------------------------------------------------------------- utilidades ----

def e(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return re.sub(r"[^\w]", "", "".join(c for c in t if not unicodedata.combining(c)))


def js(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def carregar_estilo(nome: str | None, marca: dict) -> dict:
    nome = nome or (marca.get("motion") or {}).get("estilo") or "escuro"
    arq = ESTILOS / f"{nome}.json"
    if not arq.exists():
        raise SystemExit(f"estilo de motion desconhecido: {nome} (opções: {', '.join(p.stem for p in ESTILOS.glob('*.json'))})")
    est = json.loads(arq.read_text(encoding="utf-8"))
    cores = marca.get("cores") or {}
    if cores.get("destaque"):
        est["vars"]["--destaque"] = cores["destaque"]
        est["vars"]["--sobre-destaque"] = "#111111" if _lum(cores["destaque"]) > 0.5 else "#ffffff"
    if cores.get("secundaria"):
        est["vars"]["--destaque-2"] = cores["secundaria"]
    if cores.get("fundo_card"):
        est["vars"]["--bg"] = cores["fundo_card"]
    if marca.get("fonte_titulo"):
        f = marca["fonte_titulo"]
        # arquivo mais pesado da família (Black/ExtraBold) para os títulos
        candidatos = [p for p in FONTES.glob("*.ttf") if p.stem.rsplit("-", 1)[0].lower() == f.replace(" ", "").lower()]
        arq_f = max(candidatos, key=lambda p: int(p.stem.rsplit("-", 1)[1]), default=None)
        arq_f = arq_f.name if arq_f else None
        if arq_f:
            est["fontes"]["titulo"] = [f, arq_f, 900]
    return est


def _lum(hex_cor: str) -> float:
    h = hex_cor.lstrip("#")
    if len(h) != 6:
        return 0.5
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def svg_icone(nome: str | None, estilo_icone: str) -> str:
    if not nome or estilo_icone in ("nenhum", "emoji"):
        return ""
    from icones import svg

    try:
        return svg(nome, estilo_icone)
    except SystemExit:
        return ""


def icone_html(card: dict, estilo_icone: str, classe: str = "icone-box") -> str:
    if estilo_icone == "nenhum":
        return ""
    if estilo_icone == "emoji":
        if card.get("emoji"):
            return f'<div class="{classe}"><span class="emoji">{e(card["emoji"])}</span></div>'
        return ""
    s = svg_icone(card.get("icone"), estilo_icone)
    return f'<div class="{classe}">{s}</div>' if s else ""


# -------------------------------------------------------------- sincronia ----

def achar_palavra(palavras: list[dict], alvo: str, depois: float, antes: float) -> float | None:
    """Início da primeira palavra falada que bate com `alvo` (aceita 1–3 palavras) no intervalo."""
    alvo_n = [_norm(x) for x in str(alvo).split() if _norm(x)]
    if not alvo_n:
        return None
    for i, w in enumerate(palavras):
        if w["start"] < depois - 0.3 or w["start"] > antes:
            continue
        seq = [_norm(x["text"]) for x in palavras[i:i + len(alvo_n)]]
        if all(s.startswith(a) or a.startswith(s) and len(s) >= 3 for s, a in zip(seq, alvo_n)) and len(seq) == len(alvo_n):
            return round(w["start"], 3)
    return None


def resolver_sincronia(card: dict, palavras: list[dict], avisos: list[str]) -> None:
    a, b = card["inicio"], card["fim"]
    c = card.setdefault("campos", {})

    def resolver(obj: dict, chave: str, nome: str) -> None:
        if obj.get("em") is not None:
            return
        if obj.get(chave):
            t = achar_palavra(palavras, obj[chave], a, b)
            if t is None:
                avisos.append(f"{card['id']}: não achei a palavra \"{obj[chave]}\" falada entre {a:.1f}s e {b:.1f}s ({nome})")
            else:
                obj["em"] = t

    resolver(c, "falada" if card["tipo"] == "palavra" else "palavra", "card")
    for lista in ("itens", "passos"):
        for i, it in enumerate(c.get(lista) or []):
            if isinstance(it, str):
                c[lista][i] = it = {"texto": it}
            resolver(it, "palavra", f"{lista} {i + 1}")


def validar(roteiro: dict, palavras: list[dict], duracao: float) -> list[str]:
    avisos: list[str] = []
    ids = set()
    for i, card in enumerate(roteiro.get("cards", [])):
        card.setdefault("id", f"card-{i + 1:02d}")
        if card["id"] in ids:
            avisos.append(f"{card['id']}: id repetido")
        ids.add(card["id"])
        tipo = card.get("tipo")
        if tipo not in TIPOS:
            avisos.append(f"{card['id']}: tipo \"{tipo}\" não existe ({', '.join(TIPOS)})")
            continue
        man = json.loads((MODELOS / tipo / "manifesto.json").read_text(encoding="utf-8"))
        for campo, info in man["campos"].items():
            if info.get("obrigatorio") and not card.get("campos", {}).get(campo):
                avisos.append(f"{card['id']}: falta o campo \"{campo}\" ({man['nome']})")
        card["inicio"] = max(0.0, float(card.get("inicio", 0)))
        card["fim"] = min(duracao, float(card.get("fim", card["inicio"] + 3)))
        if card["fim"] - card["inicio"] < man.get("duracao_minima", 1.0) - 0.05:
            avisos.append(f"{card['id']}: dura {card['fim'] - card['inicio']:.1f}s, o mínimo do modelo é {man['duracao_minima']}s")
        resolver_sincronia(card, palavras, avisos)
    return avisos


def tempo_cheio(card: dict) -> float:
    """Instante em que o card está completo (todos os itens na tela): usado na prévia e na medição."""
    c = card.get("campos", {})
    a = card["inicio"]
    t0 = c["em"] if c.get("em") is not None else a
    # quanto cada modelo leva para terminar de montar depois do disparo
    extra = {"apresentacao": 2.0, "titulo": 0.7, "numero": 1.4, "destaque": 1.0, "palavra": 1.1,
             "chamada-final": 1.2, "lista": 0.9, "passos": 0.9, "personalizado": 1.2}.get(card["tipo"], 1.0)
    ts = [t0 + extra, a + 1.0]
    for lista in ("itens", "passos"):
        for it in c.get(lista) or []:
            if isinstance(it, dict) and it.get("em") is not None:
                ts.append(it["em"] + 0.7)
    if card["tipo"] in ("titulo", "destaque"):
        n = len(str(c.get("titulo") or c.get("frase") or "").split())
        ts.append(t0 + 0.4 + n * 0.09 + 0.6)
    return round(min(max(ts), card["fim"] - 0.35), 3)


# ------------------------------------------------------------ posicionamento ----

def caixas_rosto(layout: dict, a: float, b: float) -> list[float] | None:
    """União das caixas do rosto (x0, y0, x1, y1) no intervalo do card."""
    r = layout.get("rosto") or {}
    amostras = [c for c in (r.get("caixas") or []) if a - 0.3 <= c[0] <= b + 0.3]
    if amostras:
        return [min(c[1] for c in amostras), min(c[2] for c in amostras),
                max(c[1] + c[3] for c in amostras), max(c[2] + c[4] for c in amostras)]
    return r.get("uniao")


def zona_card(card: dict, layout: dict, ocupacao: list[tuple]) -> dict:
    """Retângulo livre para o card: longe do rosto e da legenda."""
    W, H = layout["largura"], layout["altura"]
    formato = layout["formato"]
    a, b = card["inicio"], card["fim"]
    rosto = caixas_rosto(layout, a, b)
    ajuste = card.get("_ajuste", {})

    if formato == "react" and layout.get("areas", {}).get("referencia"):
        rx, ry, rw, rh = layout["areas"]["referencia"]
        vx, vy, vw, vh = layout["areas"]["voce"]
        if layout.get("posicao") == "pip":
            rw = vx - rx  # só a parte da referência sem o quadradinho
        m = int(min(rw, rh) * 0.06)
        topo, base = ry + m, ry + rh - m
        costura = layout.get("costura")
        if costura and layout.get("orientacao") == "vertical":
            if ry < costura:
                base = min(base, costura - 110)
            else:
                topo = max(topo, costura + 110)
        w = min(rw - 2 * m, 960)
        k = min(1.0, w / 600) * (0.95 if layout.get("orientacao") == "vertical" else 1.0)
        return {"x": rx + (rw - w) // 2, "y": topo, "w": w, "maxh": base - topo, "lado": "topo",
                "k": round(k * ajuste.get("escala", 1.0), 3), "compacto": layout.get("orientacao") == "vertical",
                "origem": "top center"}

    if H > W:  # vertical: faixa de cima, acima do rosto (UI do Reels ocupa y < 90)
        m = 60
        topo = 96
        limite = (rosto[1] - 24) if rosto else int(H * 0.2)
        maxh = max(limite - topo, 230)
        w = W - 2 * m
        k = 1.12 * ajuste.get("escala", 1.0)
        return {"x": m, "y": topo, "w": w, "maxh": maxh, "lado": "topo", "k": round(k, 3),
                "compacto": True, "origem": "top center"}

    # horizontal: lateral oposta ao rosto, fora dos 20% de baixo (legenda)
    m = int(W * 0.036)
    topo = int(H * 0.157)
    base = int(H * 0.80) - 20
    x0, x1 = (rosto[0], rosto[2]) if rosto else (W * 0.36, W * 0.64)
    folga = int(W * 0.016)
    livre = {"esquerda": (m, int(x0) - folga), "direita": (int(x1) + folga, W - m)}
    larg = {lado: max(0, r[1] - r[0]) for lado, r in livre.items()}
    pref = card.get("lado") if card.get("lado") in livre else ajuste.get("lado")
    if pref not in livre:
        ordem = sorted(livre, key=lambda s: -larg[s])
        # evita dois cards ao mesmo tempo no mesmo lado
        ocupados = {lado for (lado, ia, ib) in ocupacao if ia < b and a < ib}
        pref = next((s for s in ordem if s not in ocupados and larg[s] >= W * 0.2), ordem[0])
    wmax = int(W * 620 / 1920)
    w = max(min(wmax, larg[pref]), int(W * 0.17))
    k = min(1.03, w / (600 * W / 1920)) * (W / 1920) * ajuste.get("escala", 1.0)
    x = livre[pref][0] if pref == "esquerda" else livre[pref][1] - w
    return {"x": int(x), "y": topo, "w": w, "maxh": base - topo, "lado": pref, "k": round(k, 3),
            "compacto": False, "origem": "top left" if pref == "esquerda" else "top right",
            "apertado": larg[pref] < W * 0.17}


# -------------------------------------------------------------- modelos ----

def _chars(texto: str) -> str:
    return "".join(f'<span class="char">{e(ch) if ch != " " else "&nbsp;"}</span>' for ch in texto)


def _palavras(texto: str, destaque: str | None = None) -> str:
    alvo = [_norm(x) for x in (destaque or "").split()]
    partes = []
    toks = texto.split()
    i = 0
    while i < len(toks):
        n = len(alvo)
        if n and [_norm(t) for t in toks[i:i + n]] == alvo:
            for t in toks[i:i + n]:
                partes.append(f'<span class="palavra-anim destaque-cor">{e(t)}</span>')
            i += n
            continue
        partes.append(f'<span class="palavra-anim">{e(toks[i])}</span>')
        i += 1
    return "".join(partes)


CHECK_SVG = '<svg viewBox="0 0 40 40"><path d="M8 21 L17 30 L33 11" /></svg>'


def modelo(card: dict, est: dict, marca: dict, icones: str, zona: dict) -> tuple[str, str]:
    """(html de dentro do .root, js da animação). No js: I = id, A = início, B = fim."""
    tipo, c = card["tipo"], card.get("campos", {})
    anim = est["animacao"]
    ic = icone_html(card, icones)
    kicker = c.get("kicker")

    def cab(k: str | None) -> str:
        if not k and not ic:
            return ""
        return f'<div class="cabeca">{ic}<div class="kicker">{e(k or "")}</div></div>'

    if tipo == "apresentacao":
        arroba = c.get("arroba") or marca.get("arroba")
        h = (cab(kicker or "Me chamo") + f'<div class="nome titulo-fonte">{_chars(c.get("nome", ""))}</div>'
             '<div class="barra"></div>'
             + (f'<div class="sub">{e(c["subtitulo"])}</div>' if c.get("subtitulo") else "")
             + (f'<div class="arroba">{e(arroba)}</div>' if arroba else ""))
        t_nome = c.get("em", None)
        j = f"""
const tn = {js(t_nome)} !== null ? Math.max(A + 0.15, {js(t_nome)} - 0.1) : A + 0.3;
tl.from(sel(".nome .char"), {{opacity: 0, y: 14 * K, scale: .8, duration: .35, ease: "power2.out", stagger: .045}}, tn);
tl.fromTo(sel(".barra"), {{width: 0}}, {{width: 220 * K, duration: .5, ease: "power3.out"}}, tn + .6);
tl.from(sel(".sub"), {{opacity: 0, y: 16 * K, duration: .45, ease: "power3.out"}}, tn + 1.0);
tl.from(sel(".arroba"), {{opacity: 0, scale: .6, duration: .45, ease: MOLA}}, tn + 1.35);"""
        return h, j

    if tipo == "titulo":
        h = cab(kicker) + f'<div class="titulo titulo-fonte">{_palavras(c.get("titulo", ""), c.get("destaque"))}</div>'
        j = f"""
const t0 = {js(c.get("em"))} !== null ? {js(c.get("em"))} : A + .2;
tl.from(sel(".titulo .palavra-anim"), {{opacity: 0, y: 30 * K, duration: .45, ease: ENT, stagger: .09}}, t0);
tl.from(sel(".destaque-cor"), {{color: "inherit", duration: .4, ease: "power1.out"}}, t0 + .5);"""
        return h, j

    if tipo == "lista":
        itens = c.get("itens") or []
        h = cab(c.get("titulo") or kicker) + '<div class="itens">' + "".join(
            f'<div class="item" id="{card["id"]}-i{n}"><div class="check">{CHECK_SVG}</div>{e(it.get("texto", ""))}</div>'
            for n, it in enumerate(itens, start=1)) + "</div>"
        tempos = []
        passo = max(0.6, (card["fim"] - card["inicio"] - 1.0) / max(1, len(itens)))
        for n, it in enumerate(itens):
            tempos.append(it.get("em") if it.get("em") is not None else card["inicio"] + 0.6 + n * passo)
        j = f"""
{js(tempos)}.forEach(function (t, n) {{
  const item = "#" + I + "-i" + (n + 1), caminho = item + " path";
  const el = document.querySelector(caminho), L = el ? el.getTotalLength() : 40;
  tl.fromTo(item, {{opacity: 0, x: 40 * K * DIR}}, {{opacity: 1, x: 0, duration: .4, ease: ENT}}, t - .1);
  tl.fromTo(caminho, {{strokeDasharray: L, strokeDashoffset: L}}, {{strokeDashoffset: 0, duration: .35, ease: "power2.inOut"}}, t + .15);
}});"""
        return h, j

    if tipo == "numero":
        valor = float(c.get("valor", 0))
        casas = int(c.get("casas", 0 if float(valor).is_integer() else 1))
        barra = c.get("barra")
        pct = max(0.0, min(100.0, float(barra))) if barra is not None else 0.0
        barra_js = ("tl.fromTo(sel('.enche'), {width: '0%'}, {width: '" + f"{pct:g}" + "%', duration: 1.2, ease: 'power2.out'}, t0);"
                    if barra is not None else "")
        h = (cab(c.get("rotulo") or kicker)
             + '<div class="linha-num titulo-fonte">'
             + (f'<span class="afixo">{e(c["prefixo"])}</span>' if c.get("prefixo") else "")
             + f'<span class="num">{e(_fmt_num(float(c.get("de", 0)), casas))}</span>'
             + (f'<span class="afixo">{e(c["sufixo"])}</span>' if c.get("sufixo") else "") + "</div>"
             + ('<div class="trilho"><div class="enche"></div></div>' if barra is not None else "")
             + (f'<div class="legenda-num">{e(c["legenda"])}</div>' if c.get("legenda") else ""))
        j = f"""
const t0 = {js(c.get("em"))} !== null ? {js(c.get("em"))} - .05 : A + .35;
const alvo = document.querySelector(sel(".num")), o = {{v: {float(c.get("de", 0))}}};
const fmt = function (v) {{ return v.toLocaleString("pt-BR", {{minimumFractionDigits: {casas}, maximumFractionDigits: {casas}}}); }};
tl.to(o, {{v: {valor}, duration: 1.2, ease: "power2.out", onUpdate: function () {{ alvo.textContent = fmt(o.v); }}}}, t0);
tl.set(alvo, {{textContent: fmt({valor})}}, t0 + 1.21);
tl.fromTo(sel(".linha-num"), {{scale: .7, transformOrigin: "left bottom"}}, {{scale: 1, duration: 1.2, ease: "power2.out"}}, t0);
{barra_js}
tl.from(sel(".legenda-num"), {{opacity: 0, y: 12 * K, duration: .4, ease: ENT}}, t0 + .9);"""
        return h, j

    if tipo == "destaque":
        h = (f'<div class="aspas">{svg_icone("quotes", "preenchido")}</div>'
             f'<div class="frase titulo-fonte">{_palavras(c.get("frase", ""), c.get("destaque"))}</div>'
             + (f'<div class="autor">— {e(c["autor"])}</div>' if c.get("autor") else ""))
        j = """
tl.from(sel(".aspas"), {opacity: 0, scale: .4, rotation: -15, duration: .5, ease: MOLA}, A + .1);
tl.from(sel(".frase .palavra-anim"), {opacity: 0, y: 18 * K, duration: .35, ease: ENT, stagger: .08}, A + .35);
tl.from(sel(".autor"), {opacity: 0, x: -20 * K, duration: .4, ease: ENT}, A + .6 + .08 * document.querySelectorAll(sel(".frase .palavra-anim")).length);"""
        return h, j

    if tipo == "passos":
        passos = c.get("passos") or []
        h = cab(c.get("titulo") or kicker) + '<div class="passos"><div class="fio-passos"></div>' + "".join(
            f'<div class="passo" id="{card["id"]}-p{n}"><div class="bola titulo-fonte">{n}</div><div>{e(p.get("texto", ""))}</div></div>'
            for n, p in enumerate(passos, start=1)) + "</div>"
        tempos = []
        passo = max(0.7, (card["fim"] - card["inicio"] - 1.0) / max(1, len(passos)))
        for n, p in enumerate(passos):
            tempos.append(p.get("em") if p.get("em") is not None else card["inicio"] + 0.6 + n * passo)
        j = f"""
const tp = {js(tempos)};
tp.forEach(function (t, n) {{
  const p = "#" + I + "-p" + (n + 1);
  tl.from(p + " .bola", {{scale: 0, duration: .45, ease: MOLA}}, t - .1);
  tl.from(p + " > div:last-child", {{opacity: 0, x: 30 * K, duration: .4, ease: ENT}}, t);
}});
const fio = document.querySelector(sel(".fio-passos")), ult = document.querySelector("#" + I + "-p" + tp.length);
if (fio && ult && tp.length > 1) {{
  const h = ult.offsetTop;
  tl.fromTo(fio, {{height: 0}}, {{height: h, duration: tp[tp.length - 1] - tp[0], ease: "none"}}, tp[0]);
}}"""
        return h, j

    if tipo == "palavra":
        h = ((ic or "") + f'<div class="grande titulo-fonte">{e(c.get("palavra", ""))}</div><div class="sublinhado"></div>'
             + (f'<div class="apoio">{e(c["apoio"])}</div>' if c.get("apoio") else ""))
        j = f"""
const t0 = {js(c.get("em"))} !== null ? {js(c.get("em"))} - .08 : A + .1;
tl.from(sel(".grande"), {{opacity: 0, scale: .3, rotation: -6, duration: .55, ease: MOLA}}, t0);
tl.from(sel(".icone-box"), {{opacity: 0, y: -20 * K, duration: .4, ease: ENT}}, t0 + .1);
tl.fromTo(sel(".sublinhado"), {{width: 0}}, {{width: "70%", duration: .45, ease: "power3.out"}}, t0 + .3);
tl.from(sel(".apoio"), {{opacity: 0, y: 12 * K, duration: .4, ease: ENT}}, t0 + .5);
tl.to(sel(".grande"), {{scale: 1.06, duration: .18, yoyo: true, repeat: 1, ease: "power1.inOut"}}, t0 + .9);"""
        return h, j

    if tipo == "chamada-final":
        acao = c.get("acao", "seguir")
        nome_ic, emoji = ACAO_ICONE.get(acao, ACAO_ICONE["seguir"])
        pil_ic = f'<span class="emoji">{emoji}</span>' if icones == "emoji" else (
            "" if icones == "nenhum" else svg_icone(card.get("icone") or nome_ic, "preenchido" if icones == "duotone" else icones))
        arroba = c.get("arroba") or marca.get("arroba") or ""
        logo = '<img class="logo" src="marca-logo.png" alt="">' if card.get("_logo") else ""
        h = (logo + f'<div class="texto-cta titulo-fonte">{e(c.get("texto", "Me siga para mais"))}</div>'
             + (f'<div class="pilula">{pil_ic}<span>{e(arroba)}</span></div>' if arroba or pil_ic else ""))
        j = f"""
const t0 = {js(c.get("em"))} !== null ? {js(c.get("em"))} : A + .15;
tl.from(sel(".logo"), {{opacity: 0, scale: .7, duration: .45, ease: MOLA}}, t0);
tl.from(sel(".texto-cta"), {{opacity: 0, y: 24 * K, duration: .45, ease: ENT}}, t0 + .1);
tl.from(sel(".pilula"), {{opacity: 0, scale: .5, duration: .5, ease: MOLA}}, t0 + .45);
tl.to(sel(".pilula"), {{scale: 1.07, duration: .25, yoyo: true, repeat: 3, ease: "power1.inOut"}}, t0 + 1.2);
tl.fromTo(sel(".pilula svg, .pilula .emoji"), {{rotation: 0}}, {{rotation: 14, duration: .12, yoyo: true, repeat: 5, ease: "power1.inOut"}}, t0 + 1.3);"""
        return h, j

    if tipo == "personalizado":
        return c.get("html", ""), c.get("js", "")
    raise SystemExit(f"tipo desconhecido: {tipo}")


def _fmt_num(v: float, casas: int) -> str:
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------- montagem ----

def css_modelo(tipo: str, seletor: str, card: dict) -> str:
    arq = MODELOS / tipo / "modelo.css"
    css = arq.read_text(encoding="utf-8") if arq.exists() else ""
    if tipo == "personalizado":
        css = card.get("campos", {}).get("css", "")
    return css.replace("{{card}}", seletor)


def montar_html(roteiro: dict, layout: dict, est: dict, marca: dict, icones: str, dur: float, fps: int,
                zonas: dict[str, dict], video_src: str | None = "input-video.mp4", fundo: str | None = None) -> str:
    W, H = layout["largura"], layout["altura"]
    fontes = {}
    for papel, (familia, arq, peso) in est["fontes"].items():
        fontes[papel] = (familia, arq, peso)
    ff = "\n".join(
        f'@font-face {{ font-family: "{fam}"; src: url("fonts/{arq}") format("truetype"); font-weight: {peso}; font-display: block; }}'
        for fam, arq, peso in {v for v in fontes.values()})
    vars_css = ";\n  ".join(f"{k}: {v}" for k, v in est["vars"].items())
    vars_css += (f';\n  --fonte-titulo: "{fontes["titulo"][0]}";\n  --fonte-texto: "{fontes["texto"][0]}";'
                 f'\n  --kicker-caixa: {"uppercase" if est.get("kicker_maiusculas", True) else "none"};')
    base = (MODELOS / "base.css").read_text(encoding="utf-8")

    hosts, css_cards, js_cards = [], [], []
    tipos_css = set()
    for n, card in enumerate(c for c in roteiro["cards"] if c.get("ativo", True)):
        cid = card["id"]
        z = zonas[cid]
        seletor = f'.card[data-card-id="{cid}"]'
        if card["tipo"] not in tipos_css or card["tipo"] == "personalizado":
            css_cards.append(css_modelo(card["tipo"], seletor, card) if card["tipo"] == "personalizado"
                             else css_modelo(card["tipo"], f'.card[data-tipo="{card["tipo"]}"]', card))
            tipos_css.add(card["tipo"])
        fit_escala = z.get("fit", 1.0)
        css_cards.append(
            f'{seletor} {{ --k: {z["k"]}; }}\n'
            f'{seletor} .fit {{ left: {z["x"]}px; top: {z["y"]}px; width: {z["w"]}px; '
            f'transform: scale({fit_escala}); transform-origin: {z["origem"]}; }}')
        inner, j = modelo(card, est, marca, icones, z)
        classes = "root" + (" fio" if est.get("fio_lateral") else "")
        comp = " compacto" if z.get("compacto") else ""
        dur_card = round(card["fim"] - card["inicio"], 3)
        hosts.append(
            f'<div id="host-{cid}" class="card-host clip" data-card-id="{cid}" data-start="{card["inicio"]:.3f}" '
            f'data-duration="{dur_card}" data-track-index="{2 + n}" '
            f'style="width:{W}px;height:{H}px;visibility:hidden;opacity:0;">\n'
            f'  <div class="card{comp}" data-card-id="{cid}" data-tipo="{card["tipo"]}"><div class="fit"><div class="{classes}">{inner}</div></div></div>\n</div>')
        dx = {"esquerda": -1, "direita": 1}.get(z["lado"], 0)
        dy = -1 if z["lado"] == "topo" else 0
        segura = card["fim"] >= dur - 0.05
        js_cards.append(f"""
// {cid}: {card['tipo']} {card['inicio']:.2f}s–{card['fim']:.2f}s ({z['lado']})
(function () {{
  const I = {js(cid)}, A = {card['inicio']:.3f}, B = {card['fim']:.3f}, K = {z['k']}, DIR = {dx or 1};
  const sel = function (s) {{ return '.card[data-card-id="' + I + '"] ' + s; }};
  entrar(I, A, {dx}, {dy});
  {j}
  {'' if segura else 'sair(I, B);'}
}})();""")

    video = ""
    if video_src:
        video = (f'<div class="video-wrapper" style="width:{W}px;height:{H}px;">'
                 f'<video id="bg-video" src="{video_src}" muted playsinline data-start="0" data-duration="{dur:.3f}" data-track-index="1"></video></div>\n'
                 f'<audio id="source-audio" src="{video_src}" data-start="0" data-duration="{dur:.3f}" data-track-index="{len(hosts) + 3}" data-volume="1"></audio>')
    elif fundo:
        video = f'<img id="fundo" class="clip" src="{fundo}" data-start="0" data-duration="{dur:.3f}" data-track-index="1" style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover;">'

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<!-- gerado por scripts/motion.py a partir de motion/roteiro.json: edite o roteiro, não este arquivo -->
<style>
{ff}
:root {{
  {vars_css}
}}
{base}
{chr(10).join(css_cards)}
</style>
</head>
<body>
<div id="stage" data-composition-id="editor-motion" data-start="0" data-duration="{dur:.3f}" data-fps="{fps}" data-width="{W}" data-height="{H}">
{video}
{chr(10).join(hosts)}
<script src="vendor/gsap.min.js"></script>
<script>
(function () {{
  const tl = window.gsap.timeline({{paused: true}});
  const ENT = {js(est['animacao']['entrada'])}, MOLA = {js(est['animacao']['mola'])};
  const DUR = {est['animacao']['duracao']}, DESL = {est['animacao']['deslocamento']};
  function host(id) {{ return '.card-host[data-card-id="' + id + '"]'; }}
  function entrar(id, a, dx, dy) {{
    tl.set(host(id), {{visibility: "visible"}}, a);
    tl.fromTo(host(id), {{opacity: 0}}, {{opacity: 1, duration: .35, ease: "power2.out"}}, a);
    tl.fromTo('.card[data-card-id="' + id + '"] .root', {{x: dx * DESL, y: dy * DESL * .7}}, {{x: 0, y: 0, duration: DUR, ease: ENT}}, a);
  }}
  function sair(id, b) {{
    tl.to(host(id), {{opacity: 0, duration: .3, ease: "power2.in"}}, b - .3);
    tl.set(host(id), {{visibility: "hidden"}}, b);
  }}
{''.join(js_cards)}
  window.__timelines = window.__timelines || {{}};
  window.__timelines["editor-motion"] = tl;
}})();
</script>
</div>
</body>
</html>
"""


def preparar_publico(pub: Path, est: dict, base_mp4: Path | None, marca: dict) -> None:
    (pub / "fonts").mkdir(parents=True, exist_ok=True)
    (pub / "vendor").mkdir(exist_ok=True)
    for _, arq, _ in est["fontes"].values():
        shutil.copy2(FONTES / arq, pub / "fonts" / arq)
    shutil.copy2(GSAP, pub / "vendor" / "gsap.min.js")
    if marca.get("logo"):
        logo = (RAIZ / marca["logo"]) if not Path(marca["logo"]).is_absolute() else Path(marca["logo"])
        if logo.exists():
            shutil.copy2(logo, pub / "marca-logo.png")
    if base_mp4:
        destino = pub / "input-video.mp4"
        if destino.exists():
            destino.unlink()
        try:
            os.link(base_mp4, destino)  # mesmo disco: sem ocupar espaço de novo
        except OSError:
            shutil.copy2(base_mp4, destino)


def medir(pub: Path, W: int, H: int, tempos: dict[str, float]) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(tempos, f)
        arq = f.name
    try:
        r = subprocess.run(["node", str(RAIZ / "scripts" / "medir_cards.mjs"), str(pub / "index.html"), str(W), str(H), arq],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
        if r.returncode:
            print("aviso: não consegui medir os cards (" + (r.stderr or "")[-300:].strip() + ")")
            return {}
        return json.loads(r.stdout or "{}")
    finally:
        os.unlink(arq)


def _sobrepoe(a: list, b: list, margem: int = 0) -> bool:
    return not (a[2] + margem <= b[0] or b[2] + margem <= a[0] or a[3] + margem <= b[1] or b[3] + margem <= a[1])


def zona_legenda(layout: dict) -> list[int]:
    W, H = layout["largura"], layout["altura"]
    leg = layout.get("legenda") or {}
    if leg.get("centro_y"):
        return [0, leg["centro_y"] - 70, W, leg["centro_y"] + 70]
    base = H - leg.get("margem_v", int(H * 0.08))
    alt = int(H * (0.045 if H > W else 0.07))
    return [0, base - alt * 2, W, base + 10]


def montar(trab: Path, formato: str, estilo: str | None, icones: str | None, medir_cards: bool = True) -> dict:
    lay_arq = trab / formato / "layout.json"
    if not lay_arq.exists():
        raise SystemExit(f"falta o layout do formato {formato}: rode o layout antes")
    layout = json.loads(lay_arq.read_text(encoding="utf-8"))
    rot_arq = trab / "motion" / "roteiro.json"
    if not rot_arq.exists():
        raise SystemExit(f"falta o roteiro: {rot_arq}")
    roteiro = json.loads(rot_arq.read_text(encoding="utf-8"))
    marca = ler_marca()
    est = carregar_estilo(estilo or roteiro.get("estilo"), marca)
    icones = icones or roteiro.get("icones") or (marca.get("motion") or {}).get("icones") or est.get("icones", "duotone")
    base_mp4 = trab / formato / "base.mp4"
    info = info_video(base_mp4)
    dur = info["duracao"]
    palavras = json.loads((trab / "palavras.json").read_text(encoding="utf-8"))
    avisos = validar(roteiro, palavras, dur)
    rot_arq.write_text(json.dumps(roteiro, indent=1, ensure_ascii=False), encoding="utf-8")  # grava os "em" resolvidos

    pub = trab / "motion" / formato / "public"
    if pub.exists():
        shutil.rmtree(pub)
    preparar_publico(pub, est, base_mp4, marca)
    tem_logo = (pub / "marca-logo.png").exists()
    cards = [c for c in roteiro["cards"] if c.get("ativo", True)]
    for c in cards:
        c["_logo"] = tem_logo
    if layout["altura"] > layout["largura"] or layout["formato"] == "react":
        # uma faixa só para os cards: se dois se encostam no tempo, o anterior sai antes do próximo entrar
        ordem = sorted(cards, key=lambda c: c["inicio"])
        for c, prox in zip(ordem, ordem[1:]):
            if c["fim"] > prox["inicio"] - 0.05:
                if prox["inicio"] - c["inicio"] < 1.0:
                    avisos.append(f"{c['id']} e {prox['id']} começam quase juntos; no {formato} só cabe um por vez")
                c["fim"] = round(max(c["inicio"] + 0.8, prox["inicio"] - 0.05), 3)

    ajustes: dict[str, dict] = {}
    proibidas = {"legenda": zona_legenda(layout)}
    for rodada in range(3):
        zonas, ocupacao = {}, []
        for c in cards:
            c["_ajuste"] = ajustes.get(c["id"], {})
            z = zona_card(c, layout, ocupacao)
            z["fit"] = c["_ajuste"].get("fit", 1.0)
            zonas[c["id"]] = z
            ocupacao.append((z["lado"], c["inicio"], c["fim"]))
            if z.get("apertado") and rodada == 0:
                avisos.append(f"{c['id']}: pouco espaço livre ao lado do rosto; o card fica menor")
        (pub / "index.html").write_text(
            montar_html({"cards": cards}, layout, est, marca, icones, dur, info["fps_int"], zonas), encoding="utf-8")
        if not medir_cards or not cards:
            break
        caixas = medir(pub, layout["largura"], layout["altura"], {c["id"]: tempo_cheio(c) for c in cards})
        mudou = False
        for c in cards:
            cx = caixas.get(c["id"])
            if not cx:
                continue
            z = zonas[c["id"]]
            ret = [cx["x"], cx["y"], cx["x"] + cx["w"], cx["y"] + cx["h"]]
            rosto = caixas_rosto(layout, c["inicio"], c["fim"])
            limite_base = z["y"] + z["maxh"]
            estouro = ret[3] > limite_base + 2
            bate_rosto = bool(rosto) and _sobrepoe(ret, rosto, 0) and layout["formato"] != "react"
            bate_leg = _sobrepoe(ret, proibidas["legenda"])
            if estouro or bate_leg or bate_rosto:
                aj = ajustes.setdefault(c["id"], {})
                altura_nat = cx["h"] / z.get("fit", 1.0)
                alvo = max(0.55, min(1.0, (limite_base - z["y"]) / altura_nat * 0.98))
                if bate_rosto and layout["altura"] <= layout["largura"] and not aj.get("trocou"):
                    aj["lado"] = "direita" if z["lado"] == "esquerda" else "esquerda"
                    aj["trocou"] = True
                elif alvo < aj.get("fit", 1.0) - 0.01:
                    aj["fit"] = round(alvo, 3)
                else:
                    continue
                mudou = True
            c["_medida"] = cx
        if not mudou:
            break
    # verificação final
    for c in cards:
        cx = c.get("_medida")
        if not cx:
            continue
        ret = [cx["x"], cx["y"], cx["x"] + cx["w"], cx["y"] + cx["h"]]
        rosto = caixas_rosto(layout, c["inicio"], c["fim"])
        if rosto and layout["formato"] != "react" and _sobrepoe(ret, rosto, 0):
            avisos.append(f"{c['id']}: encosta no rosto; confira na prévia (dá para usar \"lado\" ou encurtar o texto)")
        if _sobrepoe(ret, proibidas["legenda"]):
            avisos.append(f"{c['id']}: encosta na área da legenda; confira na prévia")

    resumo = {"formato": formato, "estilo": est["id"], "icones": icones, "duracao": round(dur, 3),
              "fps": info["fps_int"], "cards": [{"id": c["id"], "tipo": c["tipo"], "inicio": c["inicio"], "fim": c["fim"],
                                                   "cheio": tempo_cheio(c), "lado": zonas[c["id"]]["lado"],
                                                   "escala": zonas[c["id"]].get("fit", 1.0),
                                                   "caixa": c.get("_medida")} for c in cards],
              "avisos": avisos}
    (trab / "motion" / formato / "montagem.json").write_text(json.dumps(resumo, indent=1, ensure_ascii=False), encoding="utf-8")
    lint = subprocess.run([*bin_hyperframes(), "lint", str(pub)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    saida_lint = re.sub(r"\x1b\[[0-9;]*m", "", (lint.stdout or "") + (lint.stderr or ""))
    erros = [l for l in saida_lint.splitlines() if re.search(r"\berror\b|✗", l, re.I)]
    resumo["lint_ok"] = lint.returncode == 0 and not erros
    if not resumo["lint_ok"]:
        avisos.append("lint do HyperFrames: " + " | ".join(erros[:5] or saida_lint.strip().splitlines()[-3:]))
    return resumo


# --------------------------------------------------------- prévia / render ----

def snapshot(pub: Path, tempos: list[float], saida: Path) -> list[Path]:
    if saida.exists():
        shutil.rmtree(saida)
    at = ",".join(f"{t:.2f}" for t in tempos)
    r = subprocess.run([*bin_hyperframes(), "snapshot", str(pub), "--at", at, "--no-end", "--describe", "false",
                        "-o", str(saida)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       )
    fotos = sorted(saida.glob("*.png"), key=lambda p: _tempo_do_nome(p.name))
    if r.returncode or not fotos:
        raise SystemExit("falhou a prévia do motion:\n" + re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + (r.stderr or ""))[-1500:])
    return fotos


def _tempo_do_nome(nome: str) -> float:
    m = re.findall(r"(\d+(?:[.,]\d+)?)", nome)
    return float(m[-1].replace(",", ".")) if m else 0.0


def folha(fotos: list[Path], rotulos: list[str], destino: Path, colunas: int | None = None) -> None:
    from PIL import Image, ImageDraw, ImageFont

    imgs = [Image.open(p).convert("RGB") for p in fotos]
    w0, h0 = imgs[0].size
    alvo_w = 640 if w0 >= h0 else 360
    esc = alvo_w / w0
    tw, th = alvo_w, int(h0 * esc)
    colunas = colunas or (3 if w0 >= h0 else 4)
    colunas = min(colunas, len(imgs))
    linhas = (len(imgs) + colunas - 1) // colunas
    faixa = 44
    folha_img = Image.new("RGB", (colunas * tw + (colunas + 1) * 12, linhas * (th + faixa) + (linhas + 1) * 12), (10, 10, 10))
    try:
        fonte = ImageFont.truetype(str(FONTES / "Inter-700.ttf"), 22)
    except OSError:
        fonte = ImageFont.load_default()
    d = ImageDraw.Draw(folha_img)
    for i, (im, rot) in enumerate(zip(imgs, rotulos)):
        x = 12 + (i % colunas) * (tw + 12)
        y = 12 + (i // colunas) * (th + faixa + 12)
        d.rectangle([x, y, x + tw, y + faixa - 6], fill=(196, 255, 94))
        d.text((x + 12, y + 8), rot, fill=(0, 0, 0), font=fonte)
        folha_img.paste(im.resize((tw, th), Image.LANCZOS), (x, y + faixa))
    destino.parent.mkdir(parents=True, exist_ok=True)
    folha_img.save(destino, quality=88)


def previa(trab: Path, formato: str) -> Path:
    montagem = json.loads((trab / "motion" / formato / "montagem.json").read_text(encoding="utf-8"))
    pub = trab / "motion" / formato / "public"
    cards = montagem["cards"]
    if not cards:
        raise SystemExit("roteiro sem cards ativos")
    fotos = snapshot(pub, [c["cheio"] for c in cards], trab / "motion" / formato / "snapshots")
    rot = [f"{n}. {c['tipo']}  {c['inicio']:.1f}s–{c['fim']:.1f}s" for n, c in enumerate(cards, start=1)]
    destino = trab / "motion" / formato / "previa.jpg"
    folha(fotos, rot, destino)
    return destino


def render(trab: Path, formato: str) -> Path:
    montagem = json.loads((trab / "motion" / formato / "montagem.json").read_text(encoding="utf-8"))
    pub = trab / "motion" / formato / "public"
    destino = trab / formato / "animado.mp4"
    r = subprocess.run([*bin_hyperframes(), "render", str(pub), "-o", str(destino), "--fps", str(montagem["fps"]),
                        "--quiet"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not destino.exists():
        raise SystemExit("falhou o render do motion:\n" + re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + (r.stderr or ""))[-2000:])
    return destino


# ------------------------------------------------------------------ galeria ----

AMOSTRA = {"id": "amostra", "tipo": "lista", "icone": "lightbulb", "emoji": "💡",
           "campos": {"titulo": "3 dicas rápidas", "itens": [{"texto": "Grave em pé"}, {"texto": "Olhe para a lente"},
                                                               {"texto": "Corte as pausas"}]}}


def galeria(trab: Path, formato: str, tipo: str = "estilos") -> Path:
    """Mesmo card de exemplo (ou o 1º card do roteiro) em cada estilo, sobre um quadro do vídeo."""
    lay = json.loads((trab / formato / "layout.json").read_text(encoding="utf-8"))
    base_mp4 = trab / formato / "base.mp4"
    marca = ler_marca()
    rot_arq = trab / "motion" / "roteiro.json"
    exemplo = dict(AMOSTRA)
    if rot_arq.exists():
        cards = [c for c in json.loads(rot_arq.read_text(encoding="utf-8")).get("cards", [])
                 if c.get("tipo") in ("lista", "titulo", "numero", "passos", "destaque")]
        if cards:
            exemplo = json.loads(json.dumps(cards[0]))
    for chave in ("em",):
        exemplo.get("campos", {}).pop(chave, None)
    for lista in ("itens", "passos"):
        for it in exemplo.get("campos", {}).get(lista) or []:
            if isinstance(it, dict):
                it.pop("em", None)
                it.pop("palavra", None)

    if tipo == "estilos":
        variantes = [(p.stem, None) for p in sorted(ESTILOS.glob("*.json"), key=lambda p: ["escuro", "claro", "pop", "editorial"].index(p.stem) if p.stem in ["escuro", "claro", "pop", "editorial"] else 9)]
    else:
        est_nome = (marca.get("motion") or {}).get("estilo") or "escuro"
        variantes = [(est_nome, ic) for ic in ESTILOS_ICONE]

    info = info_video(base_mp4)
    from rosto import quadro_bom

    d = info["duracao"]
    t_quadro = quadro_bom(base_mp4, [d * f for f in (0.4, 0.3, 0.5, 0.6, 0.2, 0.7, 0.8)])
    trab_gal = trab / "motion" / formato / "galeria"
    if trab_gal.exists():
        shutil.rmtree(trab_gal)
    fotos, rotulos = [], []
    for n, (est_nome, ic) in enumerate(variantes, start=1):
        est = carregar_estilo(est_nome, marca)
        icones = ic or est.get("icones", "duotone")
        pub = trab_gal / f"{n:02d}"
        preparar_publico(pub, est, None, marca)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_quadro:.2f}", "-i", str(base_mp4), "-frames:v", "1",
                        str(pub / "fundo.jpg")], check=True)
        card = json.loads(json.dumps(exemplo))
        card.update({"id": "amostra", "inicio": 0.0, "fim": 3.0, "lado": card.get("lado")})
        c = card.setdefault("campos", {})
        for lista in ("itens", "passos"):
            for i, it in enumerate(c.get(lista) or []):
                if isinstance(it, dict):
                    it["em"] = 0.3 + i * 0.25
        z = zona_card(card, {**lay}, [])
        z["fit"] = 1.0
        (pub / "index.html").write_text(montar_html({"cards": [card]}, lay, est, marca, icones, 3.0, 30, {"amostra": z},
                                                    video_src=None, fundo="fundo.jpg"), encoding="utf-8")
        foto = snapshot(pub, [2.4], pub / "snap")[0]
        fotos.append(foto)
        rotulos.append(f"{n}. {est['nome']}" if tipo == "estilos" else f"{n}. Ícones: {icones}")
    destino = trab / "motion" / formato / (f"galeria-{tipo}.jpg")
    folha(fotos, rotulos, destino, colunas=2 if tipo == "estilos" else (3 if lay["largura"] >= lay["altura"] else 5))
    return destino


# ---------------------------------------------------------------------- main ----

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["montar", "previa", "galeria", "render", "validar"])
    ap.add_argument("trabalho", type=Path)
    ap.add_argument("--formato", default="horizontal", choices=["horizontal", "vertical", "react"])
    ap.add_argument("--estilo")
    ap.add_argument("--icones", choices=ESTILOS_ICONE)
    ap.add_argument("--tipo", choices=["estilos", "icones"], default="estilos")
    ap.add_argument("--sem-medir", action="store_true")
    a = ap.parse_args()
    trab = a.trabalho.resolve()

    if a.acao == "validar":
        roteiro = json.loads((trab / "motion" / "roteiro.json").read_text(encoding="utf-8"))
        palavras = json.loads((trab / "palavras.json").read_text(encoding="utf-8"))
        dur = info_video(trab / "cortado.mp4")["duracao"]
        avisos = validar(roteiro, palavras, dur)
        print("\n".join(avisos) if avisos else "roteiro ok")
        return
    if a.acao == "montar":
        r = montar(trab, a.formato, a.estilo, a.icones, not a.sem_medir)
        print(f"motion montado: {len(r['cards'])} cards, estilo {r['estilo']}, ícones {r['icones']}, lint {'ok' if r['lint_ok'] else 'COM ERROS'}")
        for c in r["cards"]:
            print(f"  {c['id']} {c['tipo']:<13} {c['inicio']:6.2f}–{c['fim']:6.2f}s  lado {c['lado']:<8} escala {c['escala']}")
        for av in r["avisos"]:
            print("  aviso: " + av)
        return
    if a.acao == "previa":
        print(f"prévia → {previa(trab, a.formato)}")
        return
    if a.acao == "galeria":
        print(f"galeria → {galeria(trab, a.formato, a.tipo)}")
        return
    print(f"render → {render(trab, a.formato)}")


if __name__ == "__main__":
    main()
