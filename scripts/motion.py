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
TIPOS = ["apresentacao", "titulo", "lista", "numero", "destaque", "passos", "palavra", "chamada-final", "pontilhismo",
         "personalizado"]
ORDEM_ESTILOS = ["escuro", "claro", "pop", "editorial", "cinema"]
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
    for lista in ("itens", "passos", "etapas"):
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
             "chamada-final": 1.2, "lista": 0.9, "passos": 0.9, "pontilhismo": 2.0, "personalizado": 1.2}.get(card["tipo"], 1.0)
    if card["tipo"] == "pontilhismo":  # a prévia mostra o 1º desenho já formado
        t1 = tempos_etapas(card)
        if not t1:
            return round(min(a + 1.0, card["fim"] - 0.35), 3)
        fim = t1[1] - 0.05 if len(t1) > 1 else card["fim"] - 0.35
        return round(min(t1[0] + PT_MORFE + 0.6, fim), 3)
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

    if layout.get("centralizado"):  # vídeo narrado (sem câmera): card grande no meio, acima da legenda
        leg = zona_legenda(layout)
        if H > W:
            m, topo = 70, 200
            w, k = W - 2 * m, 1.75
        else:
            m, topo = int(W * 0.2), int(H * 0.1)
            w, k = W - 2 * m, 1.6 * W / 1920
        base = leg[1] - 30
        dy = int(ajuste.get("dy", 0))
        return {"x": m, "y": topo + dy, "w": w, "maxh": base - topo - dy, "lado": "topo",
                "k": round(k * ajuste.get("escala", 1.0), 3), "compacto": False, "origem": "top center",
                "faixa": (topo, base)}

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


def revelar(alvo: str, t0: str, stagger: float, y: float, dur: float = .4) -> str:
    """Entrada palavra a palavra: sobe e aparece (padrão) ou surge do desfoque (estilo com "revelar": "desfoque")."""
    return (f'if (REVELAR === "desfoque") tl.fromTo(sel("{alvo}"), {{opacity: 0, filter: "blur(14px)"}}, '
            f'{{opacity: 1, filter: "blur(0px)", duration: .75, ease: "power2.out", stagger: {stagger * 1.5:g}}}, {t0});\n'
            f'else tl.from(sel("{alvo}"), {{opacity: 0, y: {y:g} * K, duration: {dur:g}, ease: ENT, stagger: {stagger:g}}}, {t0});')


# ----------------------------------------------------------- pontilhismo ----

PT_MORFE = 1.3  # segundos que os pontos levam para trocar de desenho
PT_COLUNAS = {"baixa": 70, "media": 95, "alta": 125}
PT_MAX = 7000
FORMAS = ("circulo", "anel", "orbitas", "onda", "dispersar")


def tempos_etapas(card: dict) -> list[float]:
    """Instante em que os pontos começam a formar cada desenho."""
    etapas = card.get("campos", {}).get("etapas") or []
    a, b = card["inicio"], card["fim"]
    passo = max(PT_MORFE + 0.4, (b - a - 1.5) / max(1, len(etapas)))
    ts, ant = [], None
    for n, et in enumerate(etapas):
        t = et.get("em") if isinstance(et, dict) and et.get("em") is not None else a + 0.25 + n * passo
        t = max(t - 0.15, a + 0.1) if ant is None else max(t - 0.15, ant + PT_MORFE + 0.6)  # cada desenho fica pronto e parado um pouco
        ts.append(round(t, 3))
        ant = t
    return ts


def _caminho_imagem(card: dict, arq: str) -> Path:
    p = Path(arq)
    return p if p.is_absolute() else Path(card.get("_base", ".")) / p


def _proporcao(card: dict) -> float:
    c = card.get("campos", {})
    if c.get("proporcao"):
        return max(0.4, min(1.6, float(c["proporcao"])))
    from PIL import Image

    for et in c.get("etapas") or []:
        if isinstance(et, dict) and et.get("imagem"):
            arq = _caminho_imagem(card, et["imagem"])
            if arq.exists():
                with Image.open(arq) as im:
                    return max(0.4, min(1.6, im.height / im.width))
    return 0.75


def _recortar_pessoa(img):
    """Máscara 0..1 da pessoa (GrabCut a partir do rosto). None se não achar rosto."""
    import cv2
    import numpy as np

    rgb = np.asarray(img)
    esc = min(1.0, 520 / max(rgb.shape[:2]))
    peq = cv2.resize(rgb, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(peq, cv2.COLOR_RGB2BGR)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    rostos = casc.detectMultiScale(cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)), 1.1, 5,
                                   minSize=(int(min(peq.shape[:2]) * 0.12),) * 2)
    if len(rostos) == 0:
        return None
    x, y, w, h = max(rostos, key=lambda r: r[2] * r[3])
    H, W = peq.shape[:2]
    m = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    # cabeça e tronco provavelmente pessoa; o rosto com certeza
    x0, x1 = max(0, int(x - 0.9 * w)), min(W, int(x + 1.9 * w))
    y0 = max(0, int(y - 0.55 * h))
    m[y0:, x0:x1] = cv2.GC_PR_FGD
    m[y + h // 6:y + h * 5 // 6, x + w // 6:x + w * 5 // 6] = cv2.GC_FGD
    m[:, :max(1, x0 // 2)] = cv2.GC_BGD
    m[:, W - max(1, (W - x1) // 2):] = cv2.GC_BGD
    m[:max(1, y0 // 2), :] = cv2.GC_BGD
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, m, None, bg, fg, 5, cv2.GC_INIT_WITH_MASK)
    masc = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    masc = cv2.GaussianBlur(masc, (0, 0), 2.5)
    return cv2.resize(masc, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)


def _brilho_etapa(card: dict, et: dict, cols: int, rows: int, avisos: list[str]):
    """Grade (rows x cols) de brilho 0..1 do desenho; "dispersar" para poeira; None se não deu para montar."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    if et.get("imagem"):
        arq = _caminho_imagem(card, et["imagem"])
        if not arq.exists():
            avisos.append(f"{card['id']}: não achei a imagem {arq}")
            return None
        with Image.open(arq) as im:
            cor = ImageOps.exif_transpose(im).convert("RGB")
        g = ImageOps.autocontrast(cor.convert("L"), cutoff=1)
        mascara = _recortar_pessoa(cor) if et.get("recortar", "auto") else None
        if mascara is not None:  # foto de gente: só a pessoa vira ponto, o fundo some
            g = Image.fromarray((np.asarray(g, np.float32) * mascara).astype(np.uint8))
        else:
            a = np.asarray(g)
            borda = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
            if et.get("inverter", borda.mean() > 140):  # fundo claro (gravura, foto de estúdio): o escuro vira ponto
                g = ImageOps.invert(g)
        g.thumbnail((cols, rows), Image.LANCZOS)
        grade = np.zeros((rows, cols), np.float32)
        y0, x0 = (rows - g.height) // 2, (cols - g.width) // 2
        grade[y0:y0 + g.height, x0:x0 + g.width] = np.asarray(g, np.float32) / 255
        if et.get("vinheta", True):  # some aos poucos nas bordas, como nos retratos pontilhados
            yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
            r = np.hypot((xx - cols / 2) / (g.width / 2 + 1e-6), (yy - rows / 2) / (g.height / 2 + 1e-6))
            grade *= np.clip(1.35 - r, 0, 1)
        return grade ** 1.25
    if et.get("texto"):
        esc = 6
        img = Image.new("L", (cols * esc, rows * esc), 0)
        d = ImageDraw.Draw(img)
        texto = str(et["texto"])
        tam = rows * esc
        while True:
            fonte = ImageFont.truetype(str(FONTES / "Inter-900.ttf"), tam)
            x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=fonte)
            if (x1 - x0 <= img.width * 0.9 and y1 - y0 <= img.height * 0.7) or tam <= 8:
                break
            tam = int(tam * 0.92)
        d.text(((img.width - (x1 - x0)) / 2 - x0, (img.height - (y1 - y0)) / 2 - y0), texto, font=fonte, fill=255)
        return np.asarray(img.resize((cols, rows), Image.BOX), np.float32) / 255
    forma = et.get("forma")
    if forma in FORMAS:
        if forma == "dispersar":
            return "dispersar"
        yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
        r = np.hypot(xx - cols / 2, yy - rows / 2) / (min(cols, rows) / 2)
        if forma == "circulo":
            return np.clip((0.86 - r) * 8, 0, 1) * (0.55 + 0.45 * np.clip(1 - r, 0, 1))
        if forma == "anel":
            return np.clip(1 - np.abs(r - 0.8) / 0.07, 0, 1)
        if forma == "orbitas":
            g = np.clip((0.16 - r) * 10, 0, 1)
            for raio in (0.36, 0.58, 0.82):
                g = np.maximum(g, np.clip(1 - np.abs(r - raio) / 0.025, 0, 1) * 0.8)
            return g
        yc = rows / 2 + np.sin(xx / cols * np.pi * 4) * rows * 0.22  # onda
        return np.clip(1 - np.abs(yy - yc) / (rows * 0.07), 0, 1)
    avisos.append(f"{card['id']}: etapa sem imagem, texto ou forma ({', '.join(FORMAS)})")
    return None


def pontos_pontilhismo(card: dict, cw: int, ch: int, avisos: list[str]) -> dict:
    """Pontos (x, y, tamanho×100) de cada desenho no canvas. alvos[0] = poeira espalhada, antes do 1º desenho."""
    import numpy as np

    c = card.get("campos", {})
    cols = PT_COLUNAS.get(c.get("densidade"), PT_COLUNAS["media"])
    passo = cw / cols
    rows = max(8, int(ch / passo))
    rng = np.random.default_rng(42)

    def poeira(n: int):  # nuvem arredondada, mais densa no meio
        lado = min(cw, ch)
        x, y = rng.normal(0, lado * 0.22, n), rng.normal(0, lado * 0.22, n)
        return np.stack([cw / 2 + x * cw / lado, ch / 2 + y * ch / lado, rng.uniform(0.08, 0.3, n)], 1)

    nuvens = []
    for et in c.get("etapas") or []:
        g = _brilho_etapa(card, et, cols, rows, avisos) if isinstance(et, dict) else None
        if g is None:
            continue
        if isinstance(g, str):
            nuvens.append(None)
            continue
        ys, xs = np.nonzero(g > 0.1)
        px = (xs + 0.5 + (ys % 2) * 0.5) * passo  # linhas alternadas meio passo: trama de meio-tom
        py = (ys + 0.5) * (ch / rows)
        nuvens.append(np.stack([px, py, g[ys, xs]], 1))
    n = min(PT_MAX, max([len(v) for v in nuvens if v is not None] or [1500]))
    alvos = [poeira(n)]
    for v in nuvens:
        if v is None:
            alvos.append(poeira(n))
            continue
        if len(v) > n:
            v = v[rng.choice(len(v), n, replace=False)]
        elif len(v) < n:  # os pontos que sobram vão para cima de pontos do desenho e somem
            extra = v[rng.integers(0, len(v), n - len(v))].copy()
            extra[:, 2] = 0
            v = np.concatenate([v, extra])
        alvos.append(v[rng.permutation(n)])
    return {"n": int(n), "raio": round(passo * 0.56, 3),
            "alvos": [np.concatenate([np.round(a[:, :2]), np.round(a[:, 2:] * 100)], 1).astype(int).ravel().tolist()
                      for a in alvos]}


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
{revelar(".titulo .palavra-anim", "t0", .09, 30, .45)}
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
        j = ("""
tl.from(sel(".aspas"), {opacity: 0, scale: .4, rotation: -15, duration: .5, ease: MOLA}, A + .1);
""" + revelar(".frase .palavra-anim", "A + .35", .08, 18, .35) + """
tl.from(sel(".autor"), {opacity: 0, x: -20 * K, duration: .4, ease: ENT}, A + .6 + .08 * document.querySelectorAll(sel(".frase .palavra-anim")).length);""")
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
        # palavra longa não pode vazar do card: a fonte encolhe para caber na largura (maiúsculas ≈ 0,72 em por letra)
        n_letras = max(len(c.get("palavra", "")), 1)
        px = min(128 * zona["k"], zona["w"] * 0.84 / (n_letras * 0.72))
        h = ((ic or "") + f'<div class="grande titulo-fonte" style="font-size:{px:.0f}px">{e(c.get("palavra", ""))}</div><div class="sublinhado"></div>'
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

    if tipo == "pontilhismo":
        avisos = card.setdefault("_avisos", [])
        k = zona["k"]
        prop = _proporcao(card)
        largura = zona["w"] - 2 * 44 * k
        livre = zona["maxh"] - 2 * 38 * k - (80 * k if c.get("titulo") else 0) - (44 * k if c.get("legenda") else 0)
        cw = int(max(120, min(largura, livre / prop)))
        ch = int(cw * prop)
        dados = pontos_pontilhismo(card, cw, ch, avisos)
        tempos = tempos_etapas(card)[:len(dados["alvos"]) - 1]
        if any(t > card["fim"] - PT_MORFE - 0.3 for t in tempos):
            avisos.append(f"{card['id']}: nem todos os desenhos cabem no tempo do card (cada um precisa de ~{PT_MORFE + 0.6:.1f}s); "
                          "aumente o fim ou tire uma etapa")
        h = ((f'<div class="titulo titulo-fonte">{_palavras(c["titulo"], c.get("destaque"))}</div>' if c.get("titulo") else "")
             + f'<canvas class="pontos" width="{cw}" height="{ch}" style="width:{cw}px;margin:0 auto"></canvas>'
             + (f'<div class="legenda-pt">{e(c["legenda"])}</div>' if c.get("legenda") else ""))
        j = (revelar(".titulo .palavra-anim", "A + .2", .09, 24) + f"""
tl.from(sel(".legenda-pt"), {{opacity: 0, duration: .6, ease: "power2.out"}}, {js(tempos[0] if tempos else card["inicio"])} + 1.2);
const P = {js(dados)}, T = {js(tempos)}, M = {PT_MORFE};
const cv = document.querySelector(sel("canvas.pontos")), ctx = cv.getContext("2d");
const N = P.n, R = P.raio, cor = getComputedStyle(cv.parentNode).color;
const h1 = function (i) {{ const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }};
const atraso = new Float32Array(N), fase = new Float32Array(N), curva = new Float32Array(N);
for (let i = 0; i < N; i++) {{ atraso[i] = h1(i) * .45; fase[i] = h1(i + 7) * 6.283; curva[i] = h1(i + 13) - .5; }}
const suave = function (p) {{ return p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; }};
function desenhar(t) {{
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = cor;
  ctx.beginPath();
  let k = -1;
  for (let j = 0; j < T.length; j++) if (t >= T[j]) k = j;
  const a = P.alvos[Math.max(0, k)], b = P.alvos[k + 1] || a;
  for (let i = 0; i < N; i++) {{
    const p = k < 0 ? 0 : Math.min(1, Math.max(0, (t - T[k] - atraso[i]) / M)), q = suave(p);
    const ax = a[3 * i], ay = a[3 * i + 1], bx = b[3 * i], by = b[3 * i + 1];
    const desvio = Math.sin(Math.PI * q) * curva[i] * .35;
    let x = ax + (bx - ax) * q - (by - ay) * desvio, y = ay + (by - ay) * q + (bx - ax) * desvio;
    x += Math.sin(t * 1.1 + fase[i]) * R * .35; y += Math.cos(t * .9 + fase[i]) * R * .35;
    const r = (a[3 * i + 2] + (b[3 * i + 2] - a[3 * i + 2]) * q) / 100 * R;
    if (r < .35) continue;
    ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, 6.2832);
  }}
  ctx.fill();
}}
const o = {{t: A}};
desenhar(A);
tl.to(o, {{t: B, duration: B - A, ease: "none", onUpdate: function () {{ desenhar(o.t); }}}}, A);""")
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
                 f'\n  --kicker-caixa: {"uppercase" if est.get("kicker_maiusculas", True) else "none"};'
                 f'\n  --fonte-destaque: "{fontes.get("destaque", fontes["titulo"])[0]}";')
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
        comp = (" compacto" if z.get("compacto") else "") + (" centro" if z.get("faixa") else "")
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
{chr(10).join(est.get("css") or [])}
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
  const DUR = {est['animacao']['duracao']}, DESL = {est['animacao']['deslocamento']}, REVELAR = {js(est['animacao'].get('revelar', 'subir'))};
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
        c["_base"] = str(trab)
    if layout["altura"] > layout["largura"] or layout["formato"] == "react" or layout.get("centralizado"):
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
            if z.get("faixa") and not estouro and not bate_leg:
                # narrado: centraliza o card na altura livre (o primeiro desenho fica colado no topo)
                topo_f, base_f = z["faixa"]
                alvo_y = topo_f + max(0, (base_f - topo_f - cx["h"]) // 2)
                aj = ajustes.setdefault(c["id"], {})
                if abs(alvo_y - cx["y"]) > 8 and not aj.get("centrado"):
                    aj["dy"] = aj.get("dy", 0) + (alvo_y - cx["y"])
                    aj["centrado"] = True
                    mudou = True
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
    for c in cards:
        avisos.extend(dict.fromkeys(c.pop("_avisos", [])))
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
        variantes = [(p.stem, None) for p in sorted(ESTILOS.glob("*.json"), key=lambda p: ORDEM_ESTILOS.index(p.stem) if p.stem in ORDEM_ESTILOS else 9)]
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
        if lay.get("centralizado") and not (lay.get("fundo") or {}).get("imagem"):
            # vídeo narrado: cada estilo aparece sobre o próprio fundo (escuro, claro…)
            from narrar import gerar_fundo
            gerar_fundo(lay["largura"], lay["altura"], est, pub / "fundo.jpg")
        else:
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
